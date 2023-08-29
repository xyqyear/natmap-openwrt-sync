import os
from typing import Literal, Optional, TypedDict

from ruamel.yaml import YAML

if os.environ.get("NATMAP_SYNCER_CONFIG_PATH"):
    CONFIG_PATH = os.environ.get("NATMAP_SYNCER_CONFIG_PATH")
else:
    CONFIG_PATH = "config.yaml"


class SSHMonitorConfigT(TypedDict):
    enabled: bool
    ssh_host: Optional[str]
    ssh_user: Optional[str]
    ssh_port: Optional[int]
    ssh_key_path: Optional[str]
    ssh_poll_interval: Optional[int]


class ConfigT(TypedDict):
    bind_host: str
    bind_port: int
    ssh_monitor: SSHMonitorConfigT
    db_path: str
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


yaml = YAML(typ="safe")
with open(CONFIG_PATH) as f:
    config: ConfigT = yaml.load(f)
