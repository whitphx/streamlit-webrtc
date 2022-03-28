import subprocess

PORT = int


def start_coturn_process(
    listening_port: PORT,
    tls_listening_port: PORT,
    fingerprint: bool,
    lt_cred_mech: bool,
    server_name: str,
    realm: str,
    user: str,
):
    options_dict = {}
    options_dict["--listening-port"] = str(listening_port)
    options_dict["--tls-listening-port"] = str(tls_listening_port)
    if fingerprint:
        options_dict["--fingerprint"] = None
    if lt_cred_mech:
        options_dict["--lt-cred-mech"] = None
    options_dict["--server-name"] = server_name
    options_dict["--realm"] = realm
    options_dict["--user"] = user

    options_list = []
    for key, value in options_dict.items():
        options_list.append(key)
        if value:
            options_list.append(value)

    return subprocess.Popen(["coturn"] + options_list)
