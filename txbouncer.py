# -*- coding: utf-8 -*-

# === Imports ===
from twisted.internet import reactor
from twisted.internet.protocol import Factory, ClientFactory
from twisted.words.protocols.irc import IRC, IRCClient
import time

# === Client ===
class BouncerClientProtocol(IRCClient):
    def lineReceived(self, line):
        IRCClient.lineReceived(self, line)
        self.factory.in_buffer.append({'time':time.time(),'message':line})
        self.factory.broadcast(line)

class BouncerClient(ClientFactory):
    protocol = BouncerClientProtocol
    buffer_limit = 5000
    last_connect = 0
    def __init__(self, host, password, code):
        self.host = host
        self.password = password
        self.code = code
        self.connection = None
        self.out_buffer = []
        self.in_buffer = []
        self.connections = []
    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.performLogin = False
        p.password = self.password
        self.connection = p
        return p
    def broadcast(self, msg):
        for c in self.connections:
            c.sendLine(msg)
    def sendLine(self, msg):
        self.out_buffer.append(msg)
        self.clearBuffer()
    def clearBuffer(self):
        if not self.connection:
            return
        for msg in self.out_buffer:
            self.connection.sendLine(msg)
        self.out_buffer = []
    def connect(self, outgoing):
        for m in self.in_buffer:
            if 'time' in m and 'message' in m and m.time > last_connect - 150:
                outgoing.sendLine(m.message)
        self.connections.append(outgoing)
    def disconnect(self, outgoing):
        self.last_connect = time.time()
        self.connections.remove(outgoing)
    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        connector.connect()
    def clientConnectionFailed(self, connector, reason):
        print "Could not connect: %s" % (reason,)

# === Server ===
class BouncerServerProtocol(IRC):
    def __init__(self):
        self.out_buffer = []
        self.connection = None
    def irc_unknown(self, prefix, command, params):
        msg = ':%s %s %s' % (prefix, command, ' '.join(params)) if prefix else '%s %s' % (command, ' '.join(params))
        self.out_buffer.append(msg)
        self.clearBuffer()
    def irc_PASS(self, prefix, params):
        if self.connection:
            return self.irc_unknown(prefix, 'PASS', params)
        password = params.pop(0)
        code, chaff, host = password.rpartition('@')
        host, chaff, password = host.partition('#')
        host, chaff, port = host.partition(':')
        for c in self.factory.connections:
            if c.code == code and c.host == host:
                self.connection = c
                break
        if not self.connection:
            self.connection = self.factory.connect(host, port, password, code)
        self.connection.connect(self)
        self.clearBuffer()
    def clearBuffer(self):
        if not self.connection:
            return
        for msg in self.out_buffer:
            self.connection.sendLine(msg)
        self.out_buffer = []
    def connectionLost(self, reason):
        if self.connection:
            self.connection.disconnect(self)

class BouncerServer(Factory):
    protocol = BouncerServerProtocol
    def __init__(self):
        self.connections = []
    def connect(self, host, port, password, code):
            if not port:
                port = 6667
            if not password:
                password = None
            if not code:
                code = None
            client = BouncerClient(host, password, code)
            reactor.connectTCP(host, port, client)
            self.connections.append(client)
            return client

# === Application ===
reactor.listenTCP(6667, BouncerServer())
reactor.run()