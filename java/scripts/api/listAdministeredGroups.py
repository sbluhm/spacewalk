#!/usr/bin/python3 
from config import *
from pprint import pprint

key = login()
pprint(client.user.list_administered_system_groups(key, 'admin'))
logout(key)


