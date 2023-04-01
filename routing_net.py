from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from functools import partial
from mininet.node import RemoteController


class MyTopo(Topo):
    # create topology
    def __init__(self):
        Topo.__init__(self)
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        s5 = self.addSwitch('s5')
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')
        h6 = self.addHost('h6')

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(s1, s2, bw=1, delay='200ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s1, s3, bw=1, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s1, s4, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
        self.addLink(s2, s5)
        self.addLink(s3, s5)
        self.addLink(s4, s5)
        self.addLink(s5, h4)
        self.addLink(s5, h5)
        self.addLink(s5, h6)


def runNetwork():
    # mininet topology initialization
    topo = MyTopo()

    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, autoSetMacs=True, inNamespace=True)
    my_controller = RemoteController('co', ip='127.0.0.1', port=6653)
    net.addController(my_controller)

    net.start()

    # Dumping host connections
    dumpNodeConnections(net.hosts)
    CLI(net)  # launch simple Mininet CLI terminal window
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    runNetwork()
