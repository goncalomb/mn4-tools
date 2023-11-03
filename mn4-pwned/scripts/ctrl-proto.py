#!/usr/bin/env python3

import os, sys, enum, subprocess, selectors, struct, argparse, shlex

# These next classes implement the lower level protocol. It consists of series
# of packets, with 3 defined types: control, request and response.
# The request and response packets have an id that identifies the transaction
# this allows for multiplexed requests/responses over the same stream.
# The control packets doesn't expect a response.
#
# The protocol is not fully implemented (XXX: we don't need rest):
#  - it doesn't handle control packets
#  - it doesn't answer to requests (cannot act like a server)
#  - completely ignores 'aborted' flag on requests/responses
#
# Basically just sends requests processes responses, nothing else.

class ProtoPacketType(enum.Enum):
    CONTROL = 0
    REQUEST = 1
    RESPONSE = 2

class ProtoPacket():
    MAX_LENGTH = 0x7fff
    MAX_DATA_LENGTH = MAX_LENGTH - 4
    MAX_ID = 0x3fff

    def __init__(self, p_id=0, p_type=ProtoPacketType.CONTROL):
        self.length = 0
        self.final = False
        self.id = p_id
        self.type = p_type
        self.aborted = False
        self.data = None

    @staticmethod
    def read(data):
        if len(data) < 4:
            return None
        b0, b1 = struct.unpack('<HH', data[:4])
        if len(data) < b0 & 0x7fff:
            return None
        p = __class__()
        # b0 (byte 0): length and continuation bit
        p.length = b0 & 0x7fff
        p.final = not bool(b0 & 0x8000)
        # b1 (byte 1): id, type and aborted bit
        p.id = b1 & 0x3fff
        if b1 == 0xc000:
            p.type = ProtoPacketType.CONTROL
            p.aborted = False
        else:
            p.type = ProtoPacketType.RESPONSE if b1 & 0x8000 else ProtoPacketType.REQUEST
            p.aborted = bool(b1 & 0x4000)
        # data
        p.data = data[4:p.length]
        return p

    def write(self, f):
        self.length = len(self.data) + 4
        assert(self.length <= self.MAX_LENGTH)
        b0 = self.length if self.final else self.length & 0x8000
        b1 = 0xc000
        if self.type == ProtoPacketType.CONTROL:
            b1 = 0xc000
        else:
            if self.type == ProtoPacketType.REQUEST:
                b1 = self.id
            elif self.type == ProtoPacketType.RESPONSE:
                b1 = self.id & 0x8000
            if self.aborted:
                b1 &= 0x4000
        f.write(struct.pack('<HH', b0, b1))
        f.write(self.data)
        f.flush()

class ProtoMessageReader():
    pass

class ProtoMessageWriter():
    def __init__(self, xch, p_id, p_type):
        self._xch = xch
        self._buf = bytearray() # max packet data size
        self._p = ProtoPacket(p_id, p_type)

    def _send(self, final, aborted, data):
        self._p.final = final
        self._p.aborted = aborted
        self._p.data = data
        self._xch._write_packet(self._p)

    def write(self, data):
        self._buf.extend(data)
        l = 0
        while len(self._buf) + l > ProtoPacket.MAX_DATA_LENGTH:
            self._send(False, False, self._buf[l:l + ProtoPacket.MAX_DATA_LENGTH])
            l += ProtoPacket.MAX_DATA_LENGTH
        if l > 0:
            self._buf = self._buf[l:]

    def write_pack(self, fmt, *v):
        self.write(struct.pack(fmt, *v))

    def write_string(self, s):
        self.write(s.encode('ascii'))
        self.write(b'\x00')

    def done(self):
        self._send(True, False, self._buf)

class ProtoExchange():
    def __init__(self, f_in, f_out, dbg_in_data=None, dbg_in_packet=None, dbg_out_packet=None):
        self._f_in = f_in
        self._f_out = f_out
        self._dbg_in_data = dbg_in_data
        self._dbg_in_packet = dbg_in_packet
        self._dbg_out_packet = dbg_out_packet
        self._buf_read = bytearray()
        self._next_id = 1
        self._handlers = dict()
        self.packets_in_final = [0, 0, 0]
        self.packets_out_final = [0, 0, 0]

    def _write_packet(self, p):
        if self._dbg_out_packet:
            self._dbg_out_packet(p)
        p.write(self._f_out)
        if p.final:
            self.packets_out_final[p.type.value] += 1

    def _handle_response(self, p):
        assert(self._handlers[p.id])
        on_data, on_end = self._handlers[p.id]
        if on_data and p.data:
            on_data(p.data)
        if p.final:
            if on_end:
                on_end()
            del self._handlers[p.id]

    def _handle_packet(self, p):
        # XXX: we don't answer control or request packets
        if p.type == ProtoPacketType.CONTROL:
            raise NotImplementedError()
        elif p.type == ProtoPacketType.REQUEST:
            raise NotImplementedError()
        elif p.type == ProtoPacketType.RESPONSE:
            self._handle_response(p)
        if p.final:
            self.packets_in_final[p.type.value] += 1

    def start_request(self, on_data=None, on_end=None):
        p_id = self._next_id
        self._next_id = (self._next_id + 1) & ProtoPacket.MAX_ID or 1
        self._handlers[p_id] = on_data, on_end
        return ProtoMessageWriter(self, p_id, ProtoPacketType.REQUEST)

    def read(self):
        while r := self._f_in.read(10 * ProtoPacket.MAX_LENGTH):
            if self._dbg_in_data:
                self._dbg_in_data(r)
            self._buf_read.extend(r)
            while p := ProtoPacket.read(self._buf_read):
                self._buf_read = self._buf_read[p.length:]
                if self._dbg_in_packet:
                    self._dbg_in_packet(p)
                self._handle_packet(p)

# Implementation YellowTool/YellowBox.

class ProtoYellowRequestType(enum.Enum):
    PUSH_FILE = 1
    GET_FILE = 3
    # XXX: requires reverse engineering serialization format, not worth it
    # QUERY_INFO = 4
    DELETE_FILE = 6

class ProtoYellowResponseType(enum.Enum):
    SUCCESS = 0

class ProtoYellow(ProtoExchange):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.response_errors = 0

    def _do_request(self, on_start=None, on_data=None, on_end=None, on_error=None):
        started = False
        error_buf = None

        def on_data_wrap(data):
            nonlocal started, error_buf
            if started:
                if error_buf:
                    error_buf.extend(data)
                elif on_data:
                    on_data(data)
            else:
                if data[0] == ProtoYellowResponseType.SUCCESS.value:
                    if on_start:
                        on_start()
                    if on_data:
                        on_data(data[1:])
                else:
                    error_buf = bytearray(data)
                started = True

        def on_end_wrap():
            if error_buf:
                self.response_errors += 1
                if on_error:
                    on_error(error_buf)
            elif on_end:
                on_end()

        return self.start_request(on_data_wrap, on_end_wrap)

    def push_file(self, local, remote, on_error=None):
        writer = self._do_request(on_error=on_error)
        with open(local, 'rb') as fp:
            writer.write_pack('<B', ProtoYellowRequestType.PUSH_FILE.value)
            writer.write_string(remote)
            writer.write_pack('<B', 0) # XXX: additional options, unknown format
            while data := fp.read(ProtoPacket.MAX_DATA_LENGTH):
                writer.write(data)
        writer.done()

    def get_file(self, remote, local, on_error=None):
        fp = None

        def on_start():
            nonlocal fp
            fp = open(local, 'xb')

        def on_data(data):
            fp.write(data)

        def on_end():
            fp.close()

        writer = self._do_request(on_start, on_data, on_end, on_error)
        writer.write_pack('<B', ProtoYellowRequestType.GET_FILE.value)
        writer.write_string(remote)
        writer.write_pack('<B', 0) # XXX: position, unknown format
        # writer.write_pack('<BB', 0, 0) # XXX: position and length, unknown format
        writer.done()

    def delete_file(self, remote, on_error=None):
        writer = self._do_request(on_error=on_error)
        writer.write_pack('<B', ProtoYellowRequestType.DELETE_FILE.value)
        writer.write_string(remote)
        writer.write_pack('<B', 0) # XXX: recursive, not used
        writer.done()

# CLI stuff.

def open_serial():
    port = subprocess.check_output([os.path.join(os.path.dirname(__file__), 'ctrl-gadget.sh'), 'port']).decode('utf-8').strip()
    proc = subprocess.Popen(['socat', '-', '{},rawer'.format(port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
    return proc

def debug_in_data(d):
    print("< IN data ", end='')
    print(d)

def debug_in_packet(p):
    print("< IN packet (p.length={}, p.final={})".format(p.length, p.final))
    print("< p.id={}".format(p.id))
    print("< p.type={}".format(p.type))
    print("< p.aborted={}".format(p.aborted))
    print("< ", end='')
    print(p.data)

def debug_out_packet(p):
    print("> OUT packet (p.length={}, p.final={})".format(p.length, p.final))
    print("> p.id={}".format(p.id))
    print("> p.type={}".format(p.type))
    print("> p.aborted={}".format(p.aborted))
    print("> ", end='')
    print(p.data)

yll = None

def command_push(args):
    global yll
    def on_error(data):
        print("response error (push): ", end='', file=sys.stderr)
        print(bytes(data), file=sys.stderr)
    yll.push_file(args.local, args.remote, on_error=on_error)

def command_pull(args):
    global yll
    def on_error(data):
        print("response error (pull): ", end='', file=sys.stderr)
        print(bytes(data), file=sys.stderr)
    yll.get_file(args.remote, args.local, on_error=on_error)

def command_delete(args):
    global yll
    def on_error(data):
        print("response error (delete): ", end='', file=sys.stderr)
        print(bytes(data), file=sys.stderr)
    yll.delete_file(args.remote, on_error=on_error)

def register_commands(parser, exit_fn=None):
    subparsers = parser.add_subparsers(title='commands', dest='command')

    def register_command(cmd, fn, args=[]):
        p = subparsers.add_parser(cmd, prefix_chars=parser.prefix_chars, add_help=parser.add_help, exit_on_error=parser.exit_on_error)
        if not parser.exit_on_error:
            p.error = parser.error
        p.set_defaults(fn=fn)
        for arg in args:
            p.add_argument(arg)

    register_command('push', command_push, ['local', 'remote'])
    register_command('pull', command_pull, ['remote', 'local'])
    register_command('delete', command_delete, ['remote'])
    if exit_fn:
        register_command('exit', exit_fn)

    return subparsers

def setup(debug, repl=True):
    global yll
    running = True

    def command_exit(args):
        nonlocal running
        running = False

    parser = argparse.ArgumentParser(prefix_chars='\x00', add_help=False, exit_on_error=False)
    def parser_error(msg):
        raise argparse.ArgumentError(None, msg)
    parser.error = parser_error
    subparsers = register_commands(parser, command_exit)

    proc = open_serial()
    os.set_blocking(proc.stdout.fileno(), False)
    if debug:
        yll = ProtoYellow(proc.stdout, proc.stdin, debug_in_data, debug_in_packet, debug_out_packet)
    else:
        yll = ProtoYellow(proc.stdout, proc.stdin)

    def read_proc(fp):
        yll.read()

    def read_stdin(fp):
        parts = shlex.split(fp.readline())
        try:
            args = parser.parse_args(parts or [''])
            args.fn(args)
        except argparse.ArgumentError as e:
            print(e.message)


    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, read_proc)
    if repl:
        sel.register(sys.stdin, selectors.EVENT_READ, read_stdin)

    def run():
        while running:
            for key, events in sel.select():
                key.data(key.fileobj)
            if not repl and yll.packets_in_final[ProtoPacketType.RESPONSE.value] > 0:
                break
        proc.terminate()
        proc.wait()

    return run

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true')
    subparsers = register_commands(parser)

    args = parser.parse_args()
    if args.command:
        run = setup(args.debug, False)
        args.fn(args)
        run()
        sys.exit(1 if yll.response_errors else 0)
    else:
        setup(args.debug)()
        sys.exit(0)
