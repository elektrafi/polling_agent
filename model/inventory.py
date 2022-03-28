#!/usr/bin/env python3


# def from_sonar(
#    d: dict[
#        str,
#        str
#        | dict[
#            str,
#            list[
#                dict[
#                    str,
#                    str
#                    | dict[
#                        str,
#                        list[
#                            dict[
#                                str,
#                                str
#                                | dict[
#                                    str, str | list[dict[str, str | dict[str, str]]]
#                                ],
#                            ]
#                        ],
#                    ],
#                ]
#            ],
#        ],
#    ],
#    this: UE,
# ) -> UE:
#    logger = logging.getLogger(__name__)
#    if this.client is None:
#        this.client = Client()
#    if isinstance(d["name"], str):
#        this.client.name = d["name"]
#    if this.client.address is None:
#        this.client.address = Address()
#    if isinstance(d["id"], str):
#        this.client.sonar_id = d["id"]
#    if not isinstance(d["addresses"], dict) or not isinstance(
#        d["addresses"]["entities"], list
#    ):
#        logger.warn(f"account {this.client.sonar_id} has no servicable address")
#        return this
#    for addr in d["addresses"]["entities"]:
#        if not "id" in addr or not isinstance(addr["id"], str):
#            logger.warn(f"address id is not a string")
#        else:
#            this.client.address.sonar_id = addr["id"]
#        if not "line1" in addr or not isinstance(addr["line1"], str):
#            logger.warn(f"address line1 is not a string")
#        else:
#            this.client.address.line1 = addr["line1"]
#        if not "line2" in addr or not isinstance(addr["line2"], str):
#            logger.debug(f"address line2 is not a string")
#        else:
#            this.client.address.line2 = addr["line2"]
#        if not "city" in addr or not isinstance(addr["city"], str):
#            logger.warn(f"address city is not a string")
#        else:
#            this.client.address.city = addr["city"]
#        if not "zip" in addr or not isinstance(addr["zip"], str):
#            logger.warn(f"address zip code is not a string")
#        else:
#            this.client.address.zip_code = addr["zip"]
#        if not isinstance(addr["inventory_items"], dict) or not isinstance(
#            addr["inventory_items"]["entities"], list
#        ):
#            logger.warn(
#                f"address {this.client.address.sonar_id} has no inventory items"
#            )
#            continue
#        for item in addr["inventory_items"]["entities"]:
#            if not "id" in item or not isinstance(item["id"], str):
#                logger.warn(f"inventory item id is not a string")
#            else:
#                this.sonar_id = item["id"]
#                if this.client.sonar_id and this.client.address.sonar_id:
#                    this.linked_to_account = True
#            if not isinstance(item["inventory_model"], dict) or not isinstance(
#                item["inventory_model"]["name"], str
#            ):
#                logger.warn(
#                    f'inventory item inventory_model {item["inventory_model"]} is not a string'
#                )
#                continue
#            else:
#                model = item["inventory_model"]["name"].strip().lower()
#            if "od06" in model or "od6" in model or "bai" in model:
#                this.model = UEModel.OD06
#                this.manufacturer = UEManufacturer.BAICELLS
#            elif "6900" in model:
#                this.model = UEModel.BEC6900
#                this.manufacturer = UEManufacturer.BEC
#            elif "6500" in model:
#                this.model = UEModel.BEC6500
#                this.manufacturer = UEManufacturer.BEC
#            elif "7000" in model:
#                this.model = UEModel.BEC7000
#                this.manufacturer = UEManufacturer.BEC
#            elif "12000" in model:
#                this.model = UEModel.T12000
#                this.manufacturer = UEManufacturer.TELRAD
#            elif "12300" in model:
#                this.model = UEModel.T12300
#                this.manufacturer = UEManufacturer.TELRAD
#            if not isinstance(
#                item["inventory_model_field_data"], dict
#            ) or not isinstance(item["inventory_model_field_data"]["entities"], list):
#                logger.warn(
#                    f"inventory item {this.sonar_id} for account {this.client.sonar_id} has no mac address, imei, etc"
#                )
#                continue
#            for field in item["inventory_model_field_data"]["entities"]:
#                if not isinstance(
#                    field["inventory_model_field"], dict
#                ) or not isinstance(field["inventory_model_field"]["name"], str):
#                    logger.warn(
#                        f'inventory model field data {item["value"]} has no name'
#                    )
#                    continue
#                if not isinstance(field["value"], str):
#                    logger.warn(
#                        f'no value for inventory model field data {field["inventory_model_field"]["name"]}'
#                    )
#                    continue
#                name = field["inventory_model_field"]["name"].strip().lower()
#                if "mac" in name:
#                    this.mac_address = MACAddress(field["value"])
#                if "imei" in name:
#                    this.imei = field["value"]
#                if "imsi" in name:
#                    this.imsi = field["value"]
#                if "serial" in name:
#                    this.serial_number = field["value"]
#                if "product" in name:
#                    this.product_id = field["value"]
#                if "name" in name:
#                    this.info = field["value"]
#    logger.info(f"******** CREATED NEW ACCOUNT/INVENTORY RECORD ********\n{this}")
#    return this
