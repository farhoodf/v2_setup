import paramiko
from paramiko import SSHClient
import json
import uuid
import base64


V2RAY_URL = "https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh"
FREE_SERVER_CONFIG_PATH = "./configs/free_server_config.json"
RESTRICTED_SERVER_CONFIG_PATH = "./configs/restricted_server_config.json"


class Server:
    """docstring for Server"""
    def __init__(self, ip, username, password):
        super(Server, self).__init__()
        self.client = self.get_client(ip, username, password)
        
    def get_client(self, ip, username, password):
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=username, password=password)
        return client

    def install(self, update_first=False):
        if update_first:
            _stdin, _stdout, _stderr = self.client.exec_command("sudo apt update")
            _stdin, _stdout, _stderr = self.client.exec_command("sudo apt upgrade -y")

        _stdin, _stdout, _stderr = self.client.exec_command(f"curl -L -O {V2RAY_URL}")
        _stdin, _stdout, _stderr = self.client.exec_command("sudo chmod +x install-release.sh")
        _stdin, _stdout, _stderr = self.client.exec_command("sudo ./install-release.sh")

        _stdin, _stdout, _stderr = self.client.exec_command("v2ray version")
        stderr = _stderr.read().decode()

        return len(stderr) == 0

    def setup(self, config, port_to_open=None):
        ftp = self.client.open_sftp()
        ftp_file = ftp.file('config.json', "w", -1)
        ftp_file.write(json.dumps(config, indent=4))
        ftp_file.write('\n')
        ftp_file.flush()
        ftp.close()
        if port_to_open is not None:
            _stdin, _stdout, _stderr = self.client.exec_command(f"sudo ufw allow {port_to_open}/tcp")
        _stdin, _stdout, _stderr = self.client.exec_command("sudo cp config.json /usr/local/etc/v2ray/")
        _stdin, _stdout, _stderr = self.client.exec_command("chown 1000:1000 /usr/local/etc/v2ray/config.json")
        _stdin, _stdout, _stderr = self.client.exec_command("systemctl enable v2ray")
        _stdin, _stdout, _stderr = self.client.exec_command("systemctl start v2ray")


def get_free_server_config():
    uid = str(uuid.uuid4())
    with open(FREE_SERVER_CONFIG_PATH, 'r') as f:
        config = json.load(f)
    config['inbounds'][1]["settings"]["clients"][0]['id'] = uid
    # ToDo add custom port
    return config, uid, 443


def get_restricted_server_config(free_server_uid, free_server_ip, restricted_server_ip, free_server_port=443, num_clients=10, name="tube"):
    uri_info = {"add": restricted_server_ip,
                "port": 22220,
                "ps": name,
                "aid": "0", "alpn": "", "host": "", "net": "tcp", "path": "",
                "scy": "auto", "sni": "", "tls": "", "type": "http", "v": "2"}  

    with open(RESTRICTED_SERVER_CONFIG_PATH, 'r') as f:
        config = json.load(f)

    config["outbounds"][0]["settings"]["vnext"][0]["address"] = free_server_ip
    config["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = free_server_uid
    config["outbounds"][0]["settings"]["vnext"][0]["port"] = free_server_port

    clients = []
    uris = []
    for i in range(num_clients):
        email = f"us{i+1}"
        uid = str(uuid.uuid4())
        clients.append({'email': email, 'level': 0, 'id': uid, 'alterId': 0})
        uri_info["id"] = uid
        uri_json = json.dumps(uri_info, indent=4, sort_keys=True)
        uri = f"vmess://{base64.b64encode(uri_json.encode()).decode()}"
        uris.append([email, uri])

    config["inbounds"][1]["settings"]["clients"] = clients

    return config, uris
