from exosphere.objects import Host

inventory = [
    {
        "name": "okami",
        "ip": "okami.lab.underwares.org",
        "port": 22
    },
    {
        "name": "fenrir",
        "ip": "fenrir.underwares.org",
        "port": 22
    },
    {
        "name": "arachne",
        "ip": "arachne.lab.underwares.org",
        "port": 22
    }
]

def main() -> None:
    for host_info in inventory:
        host = Host(**host_info)
        host.sync()
        print(host)

if __name__ == "__main__":
    main()
