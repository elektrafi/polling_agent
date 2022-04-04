#!/usr/bin/env python3
from model.atoms import Model as _Model

get_inventory_items = """
        query ($page: Paginator!) {
        inventory_items(paginator:$page){
            page_info {
            page,
            total_pages,
            },
            entities{
            id
            inventory_model_field_data {
                entities {
                inventory_model_field {
                    name
                }
                value
                }
            },
            inventory_model {
                name
            }
            },
        }
        }"""

get_accounts = """
        query ($page: Paginator!) {
        accounts(paginator:$page, account_status_id:1){
            page_info {
            page,
            total_pages,
            },
            entities{
            id,
            name,
            addresses(serviceable:true){
                entities{
                id,
                line1,
                line2,
                city,
                zip,
                },
            },
            },
        }
        }"""


get_accounts_and_assigned_inventory = """
        query ($page:Paginator!) {
        accounts(paginator:$page, account_status_id:1) {
            page_info {
            page
            total_pages
            total_count
            }
            entities {
            id
            name
            addresses(serviceable: true) {
                entities {
                id
                line1
                line1
                city
                zip
                inventory_items {
                    entities {
                    id
                    inventory_model {
                        name
                    }
                    inventory_model_field_data {
                        entities {
                        inventory_model_field {
                            name
                        }
                        value
                        }
                    }
                    }
                }
                }
            }
            }
        }
        }"""

assign_inventory = """
mutation assignInventory($input: AssignInventoryItemsMutationInput, $id:[Int64Bit!]!){
    assignInventoryItems(input:$input, ids:$id){
    id,
    inventoryitemable_type,
    inventoryitemable_id,
    }
}"""

update_item_field = """
mutation update_item($id:Int64Bit!, $input:UpdateInventoryItemFieldsMutationInput) {
    updateInventoryItemFields(id:$id, input:$input) {
        id
        inventory_model{
            id
            name
        }
        inventory_model_field_data{
            entities{
                id
                inventory_model_field{
                    id
                    name
                }
                value
            }
        }
    }
}"""

update_inventory_item = """mutation update_inventory_item($id: Int64Bit!, $input: UpdateInventoryItemsMutationInput) {
  updateInventoryItem(id: $id, input: $input) {
    id
    notes {
      entities {
        message
      }
    }
  }
}
"""

create_item = """
mutation create_item($input:CreateInventoryItemsMutationInput) {
    createInventoryItems(input:$input) {
        id
    }
}"""

current_ip_address_assignments = """
query ($page:Paginator!) {
ip_assignments(paginator:$page, subnet_id:25) {
  entities{
    id
    ipassignmentable_id
    subnet
  }
}}"""

create_ip_assignment = """mutation ($input: CreateIpAssignmentMutationInput) {
  createIpAssignment(input: $input) {
    id
    subnet
    ipassignmentable_id
  }
}
"""

update_ip_assignment = """mutation ($id: Int64Bit!, $input: UpdateIpAssignmentMutationInput) {
  updateIpAssignment(id: $id, input: $input) {
    id
    subnet
    ipassignmentable_id
  }
}
"""

delete_ip_assignment = """mutation ($id: Int64Bit!) {
  deleteIpAssignment(id: $id) {
    success
    message
  }
}
"""

inventory_field_ids = {
    _Model.UNKNOWN: {},
    _Model.T12000: {
        "mac_address": 38,
        "info": 39,
        "imei": 40,
        "imsi": 41,
        "serial_number": 42,
        "product_id": 43,
    },
    _Model.T12300: {
        "mac_address": 44,
        "info": 45,
        "imei": 46,
        "imsi": 47,
        "serial_number": 48,
        "product_id": 49,
    },
    _Model.BEC6900: {
        "mac_address": 54,
        "info": 55,
        "imei": 56,
        "imsi": 57,
        "product_id": 58,
        "serial_number": 59,
    },
    _Model.BEC6500: {
        "mac_address": 60,
        "info": 61,
        "imei": 62,
        "imsi": 63,
        "product_id": 64,
        "serial_number": 65,
    },
    _Model.OD06: {
        "mac_address": 66,
        "info": 71,
        "imei": 67,
        "imsi": 68,
        "product_id": 69,
        "serial_number": 70,
    },
    _Model.BEC7000: {
        "mac_address": 72,
        "info": 73,
        "imei": 74,
        "imsi": 75,
        "product_id": 77,
        "serial_number": 76,
    },
}
