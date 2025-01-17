""" Node encapsulates the sim process, and manages process I/O. """
import os

import msgpack
import zmq

import bluesky
from bluesky import stack
from bluesky.network.common import get_hexid
from bluesky.network.npcodec import encode_ndarray, decode_ndarray
from bluesky.tools import Timer

class Node(object):
    def __init__(self, event_port, stream_port):
        self.node_id = b'\x00' + os.urandom(4)
        self.host_id = b''
        self.running = True
        ctx = zmq.Context.instance()
        self.event_io = ctx.socket(zmq.DEALER)
        self.stream_out = ctx.socket(zmq.PUB)
        self.event_port = event_port
        self.stream_port = stream_port
        # Tell bluesky that this client will manage the network I/O
        bluesky.net = self

    def event(self, eventname, eventdata, sender_id):
        ''' Event data handler. Reimplemented in Simulation. '''
        print('Node {} received {} data from {}'.format(self.node_id, eventname, sender_id))

    def step(self):
        ''' Perform one iteration step. Reimplemented in Simulation. '''
        pass

    def start(self):
        ''' Starting of main loop. '''
        # Final Initialization
        # Initialization of sockets.
        self.event_io.setsockopt(zmq.IDENTITY, self.node_id)
        self.event_io.connect('tcp://localhost:{}'.format(self.event_port))
        self.stream_out.connect('tcp://localhost:{}'.format(self.stream_port))

        # Start communication, and receive this node's ID
        self.send_event(b'REGISTER')
        self.host_id = self.event_io.recv_multipart()[0]
        print('Node started, id={}'.format(get_hexid(self.node_id)))

        # run() implements the main loop
        self.run()

    def quit(self):
        ''' Quit the simulation process. '''
        self.running = False
        self.send_event(b'QUIT')

    def run(self):
        ''' Start the main loop of this node. '''

        hex_id = get_hexid(self.node_id)

        try:
            while self.running:
                # Get new events from the I/O thread
                # while self.event_io.poll(0):
                if self.event_io.getsockopt(zmq.EVENTS) & zmq.POLLIN:
                    msg = self.event_io.recv_multipart()
                    route, eventname, data = msg[:-2], msg[-2], msg[-1]
                    # route back to sender is acquired by reversing the incoming route
                    route.reverse()
                    if eventname == b'QUIT':
                        print(f'# Node({hex_id}): Quitting (Received QUIT from server)')
                        self.quit()
                    else:
                        pydata = msgpack.unpackb(data, object_hook=decode_ndarray, raw=False)
                        self.event(eventname, pydata, route)

                # Perform a simulation step
                self.step()

                # Process timers
                Timer.update_timers()
        except KeyboardInterrupt:
            print(f'# Node({hex_id}): Quitting (KeyboardInterrupt)')
            self.quit()

    def addnodes(self, count=1):
        self.send_event(b'ADDNODES', count)

    def send_event(self, eventname, data=None, target=None):
        # On the sim side, target is obtained from the currently-parsed stack command
        target = target or stack.routetosender() or [b'*']
        pydata = msgpack.packb(data, default=encode_ndarray, use_bin_type=True)
        self.event_io.send_multipart(target + [eventname, pydata])

    def send_stream(self, name, data):
        self.stream_out.send_multipart(
            [name + self.node_id, msgpack.packb(data, default=encode_ndarray, use_bin_type=True)])
