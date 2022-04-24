# ElektraFi IPAM Arbiter and Device Information Poller
This application is a combination of a IP Address Manager and Source of Truth regarding deployed network device inventory for [Sonar](sonar.software). 

## Usage
The program can be run from any directory, but POSIX standards dictate the program be housed in `/usr/share/efi`. If the project does not already exist in that location, clone the repository.
```bash
git clone https://github.com/elektrafi/efi_polling_agent /usr/share/efi/efi_poller
```

You may need administrative or root access to write to the /usr/share/efi directory the user account you are currently using does not own the directory or is not a member of a group that owns the directory.
```bash
sudo git clone https://github.com/elektrafi.com/efi_polling_agent /usr/share/efi/efi_poller
```

For production usage, the release referenced by the `stable` tag is recommended.
```bash
git checkout stable
```

In order to maintain a persistent application after disconnecting from an SSH session, it is recommended to run the application in a tmux session. __After a server restart, the application must be restarted as well.__
```bash
tmux new -s poller
```

The main application is started via the `__main__` method of `polling_agent.py`
```bash
python polling_agent.py
```

Detach from the tmux session with `CTRL + b` followed by `d`. You can reattach to the session at any time.
```bash
tumux a -t poller
```

## Output and Logs
The application outputs high-level information to the terminal and debug-level information to 4 rotating log files that are size-limited. Not all exceptions in the output are errors, `StopIteration` errors, `ConnectionTimeoutError` errors, and SSL related errors are expected and are caused by either normal application flow or issues with Sonar's connection endpoint.

## Features
- Receives current IP address assignments from [Druid Software's Raemis](https://www.druidsoftware.com/raemis-cellular-network-technology/) (the EPC for ElektraFi's legacy LTE network)
    - Configurable between server-initiated pushed information or application-initiated pull based information on a timer
- Scans the IP addresses currently in use and collects information about the device in different ways depending on the make/model of the device
- Reports IP address attach and detach events to Sonar
- Reports requested SNMP information to Sonar
- Reports requested ICMP information to Sonar
- If a device is found on the network that is not in Sonar's inventory, the item is added to the inventory along with associated identifying information
- If the name field in the Raemis subscriber record contains the same name as a customer's account in Sonar's CRM, the found CPE is associated with the account in Sonar to allow IP address management, rate limiting, and service management operations based on Sonar's address lists
- Stores current performance metrics and other information to be used by other systems

## Information Collected
- UE
    - Identifying Information
        - Sonar ID
        - MAC Address
        - IMEI
        - IMSI
    - Connection Information
	- Cell ID
	- ECS
	- eNB ID
	- PLMN
	- Channel
	- EARFCN
	- Tx MCS
	- PCI
    - Performance Information
	- Rx data rate
	- Tx data rate
	- Current Uptime
	- Last boot time
	- sent/failed packets
	- sent/failed octets
- Data Connections via EPC
    - Subscribers
        - Name
        - Associated CPE
    - CPE
        - IMEI
        - IMSI
        - MSISDN
        - IP Address
        - Connection state
- Accounts/Subscribers
    - Name
    - Address
    - Assigned UE

## UE Information Collection Methods
- SNMP
- Web Scraping
- TR-069 Snooping
- Third party software (via API)
- SSH
- Telnet

## Integrations
### UE Devices
- BEC Devices
    - RigeWave 6500
    - RigeWave 6900
    - RigeWave 7000
- Baicells Devices
    - Atom OD06
- Telrad Devices
    - CPE12000SG
    - CPE12300SG
    - CPE12300HG
    - CPE12300XG
### EPCs
- Druid Software's Raemis
- Magma
### Information Sources
- GenieACS
