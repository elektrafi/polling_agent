# ElektraFi IPAM Arbiter and Device Information Poller
This application is a combination of a IP Address Manager and Source of Truth regarding deployed network device inventory for [Sonar](sonar.software). 

## Features
- Receives current IP address assignments from [Druid Software's Raemis](https://www.druidsoftware.com/raemis-cellular-network-technology/) (the EPC for ElektraFi's legacy LTE network)
    - Configurable betwen server-initiated pushed information or application-initated pull based information on a timer
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
