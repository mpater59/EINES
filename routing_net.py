from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import RemoteController


def runNetwork():
    # mininet topology initialization

    my_controller = RemoteController('c0', ip='127.0.0.1', port=6653)
    net = Mininet(host=CPULimitedHost, link=TCLink, autoSetMacs=True)

    # create topology
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
    s5 = net.addSwitch('s5')
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    h3 = net.addHost('h3')
    h4 = net.addHost('h4')
    h5 = net.addHost('h5')
    h6 = net.addHost('h6')

    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)
    net.addLink(s1, s2, bw=1, delay='200ms', loss=0, max_queue_size=1000, use_htb=True)
    net.addLink(s1, s3, bw=1, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
    net.addLink(s1, s4, bw=1, delay='10ms', loss=0, max_queue_size=1000, use_htb=True)
    net.addLink(s2, s5)
    net.addLink(s3, s5)
    net.addLink(s4, s5)
    net.addLink(s5, h4)
    net.addLink(s5, h5)
    net.addLink(s5, h6)

    net.addController(my_controller)

    net.start()

    # Dumping host connections
    dumpNodeConnections(net.hosts)
    CLI(net)  # launch simple Mininet CLI terminal window
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    runNetwork()
