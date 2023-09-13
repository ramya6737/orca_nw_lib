from ast import List

from orca_nw_lib.graph_db_models import Vlan
from orca_nw_lib.vlan_gnmi import get_vlan_details_from_device

from .common import VlanTagMode

from .device_db import get_device_db_obj
from .vlan_db import (
    get_vlan_obj_from_db,
    get_vlan_mem_ifcs_from_db,
    insert_vlan_in_db,
)
from .vlan_gnmi import (
    add_vlan_mem_interface_on_device,
    config_vlan_on_device,
    config_vlan_tagging_mode_on_device,
    del_vlan_from_device,
    del_vlan_mem_interface_on_device,
)
from .device_db import get_device_db_obj
from .utils import get_logging
from .graph_db_models import Vlan

_logger = get_logging().getLogger(__name__)

def create_vlan_db_obj(device_ip: str, vlan_name: str = None):
    """
    Retrieves VLAN information from a device.

    Args:
        device_ip (str): The IP address of the device.
        vlan_name (str, optional): The name of the VLAN to retrieve information for.
                                   Defaults to None.

    Returns:
        dict: A dictionary mapping Vlan objects to a list of VLAN member information.
              Each Vlan object contains information such as VLAN ID, name, MTU,
              administrative status, operational status, and autostate.
              {<vlan_db_obj>: {'ifname': 'Ethernet64', 'name': 'Vlan1', 'tagging_mode': 'tagged'}}
    """

    vlan_details = get_vlan_details_from_device(device_ip, vlan_name)
    vlans = []
    for vlan in vlan_details.get("sonic-vlan:VLAN_LIST") or []:
        vlans.append(
            Vlan(
                vlanid=vlan.get("vlanid"),
                name=vlan.get("name"),
            )
        )

    for vlan in vlan_details.get("sonic-vlan:VLAN_TABLE_LIST") or []:
        for v in vlans:
            if v.name == vlan.get("name"):
                v.mtu = vlan.get("mtu")
                v.admin_status = vlan.get("admin_status")
                v.oper_status = vlan.get("oper_status")
                v.autostate = vlan.get("autostate")

    vlans_obj_vs_mem = {}
    for v in vlans:
        members = []
        for item in vlan_details.get("sonic-vlan:VLAN_MEMBER_LIST") or []:
            if v.name == item.get("name"):
                members.append(item)
        vlans_obj_vs_mem[v] = members

    return vlans_obj_vs_mem

def _getJson(device_ip: str, v: Vlan):
    temp = v.__properties__
    temp["members"] = [
        mem.name for mem in get_vlan_mem_ifcs_from_db(device_ip, temp.get("name")) or []
    ]
    return temp


def get_vlan(device_ip, vlan_name: str = None):
    vlans = get_vlan_obj_from_db(device_ip, vlan_name)
    op_dict = []
    try:
        for v in vlans or []:
            op_dict.append(_getJson(device_ip, v))
        return op_dict
    except TypeError:
        ## Its a single vlan object no need to iterate.
        return _getJson(device_ip, vlans)


def del_vlan(device_ip, vlan_name):
    del_vlan_from_device(device_ip, vlan_name)
    discover_vlan(device_ip, vlan_name)


def config_vlan(
    device_ip: str, vlan_name: str, vlan_id: int, mem_ifs: dict[str:VlanTagMode] = None
):
    config_vlan_on_device(device_ip, vlan_name, vlan_id, mem_ifs)
    discover_vlan(device_ip, vlan_name)


def add_vlan_mem(device_ip: str, vlan_name: str, mem_ifs: dict[str:VlanTagMode]):
    add_vlan_mem_interface_on_device(device_ip, vlan_name, mem_ifs)
    discover_vlan(device_ip, vlan_name)


def get_vlan_members(device_ip, vlan_name: str):
    members = get_vlan_mem_ifcs_from_db(device_ip, vlan_name)
    mem_intf_vs_tagging_mode = {}
    for mem in members or []:
        mem_rel = get_vlan_obj_from_db(
            device_ip, vlan_name
        ).memberInterfaces.relationship(mem)
        mem_intf_vs_tagging_mode[mem.name] = mem_rel.tagging_mode
    return mem_intf_vs_tagging_mode


def config_vlan_mem_tagging(
    device_ip: str, vlan_name: str, if_name: str, tagging_mode: VlanTagMode
):
    config_vlan_tagging_mode_on_device(device_ip, vlan_name, if_name, tagging_mode)
    discover_vlan(device_ip, vlan_name)


def del_vlan_mem(device_ip: str, vlan_name: str, if_name: str = None):
    del_vlan_mem_interface_on_device(device_ip, vlan_name, if_name)
    discover_vlan(device_ip, vlan_name)




def discover_vlan(device_ip: str = None, vlan_name: str = None):
    _logger.info("Discovering VLAN.")
    devices = [get_device_db_obj(device_ip)] if device_ip else get_device_db_obj()
    for device in devices:
        _logger.info(f"Discovering VLAN on device {device}.")
        insert_vlan_in_db(device, create_vlan_db_obj(device.mgt_ip, vlan_name))
