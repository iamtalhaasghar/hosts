#!/mnt/data/projects/hosts/.venv/bin/python
# a script to generate hosts from redlib, libreddit & invidious instance pages
# Talha Asghar <talhaasghar220@gmail.com>
# 02-aug-2024

import re,io
import sys, time
from redis import Redis
from datetime import datetime
import os, requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

rdb = Redis(decode_responses=True)


prefix = f'''
# this file was autogenerated 
# on {str(datetime.now())} 
# by https://github.com/iamtalhaasghar/hosts/blob/master/generate.py
# total hosts: $total_hosts

127.0.0.1 localhost
127.0.0.1 localhost.localdomain
127.0.0.1 local
255.255.255.255 broadcasthost
::1 localhost
::1 ip6-localhost
::1 ip6-loopback
fe80::1%lo0 localhost
ff00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts
0.0.0.0 0.0.0.0
'''


def fetch_reddit_instances():
    hosts = ['https://raw.githubusercontent.com/redlib-org/redlib-instances/main/instances.json', 'https://raw.githubusercontent.com/libreddit/libreddit-instances/master/instances.json']
    for host in hosts:        
        urls = [i['url'].replace('https://', '') for i in requests.get(host).json()['instances'] if 'url' in i.keys()]
        k = '/blacklist/host/reddit'
        for u in urls:
            if not rdb.sismember(k, u):
                print(f'found new reddit instance {u} from {host}')
                rdb.sadd(k, u)

    
def fetch_invidious_instances():
    
    parser1 = lambda host: [i[0] for i in requests.get(host).json()]
    parser2 = lambda host: [i.text for i in BeautifulSoup(requests.get(host).text, 'lxml').find_all('span', class_='alias')]
    parser3 = lambda host: [re.search(r'\[(.*?)\]', i).group(1) for i in requests.get(host).text.split('\n') if i.startswith('*') and 'https' in i]

    hosts = {'https://api.invidious.io/instances.json': parser1, 'https://uptime.invidious.io' : parser2, 'https://raw.githubusercontent.com/iv-org/documentation/master/docs/instances.md': parser3}
    k = '/blacklist/host/invidious'
    for host, parser in hosts.items():
        urls = parser(host)
        #print(host, urls);continue
        for u in urls:        
            if not rdb.sismember(k, u):
                print(f'found new invidious instance {u} from {host}')
                rdb.sadd(k, u)


def block_fna_whatsapp_domains():
    '''
    Block domains like media.fkhi2-3.fna.whatsapp.net responsible for delivering media content for whatsapp channels
    '''

    if not load_dotenv():
        print("ERR: Couldn't load .env file!")
        exit()

    rdb = Redis(decode_responses=True)

    ntfy_url = os.getenv('NTFY_URL')
    # Fetch latest log entry from NextDNS analytics
    nextdns_api_key = os.getenv("NEXT_DNS_API_KEY")

    next_dns_profiles =[os.getenv("NEXT_DNS_PROFILE_PC"), os.getenv("NEXT_DNS_PROFILE_LAPTOP"), os.getenv("NEXT_DNS_PROFILE_MOBILE")]

    for next_dns_profile in next_dns_profiles:
        analytics_url = f"https://api.nextdns.io/profiles/{next_dns_profile}/logs"
        headers = {"X-Api-Key": nextdns_api_key}
        params = {"limit":1000, "sort": "desc", "status":"default", "search": "fna.whatsapp.net"}
        response = requests.get(analytics_url, headers=headers, params=params)
        data = response.json()
        domains = list()
        for row in data['data']:
            domains.append(row['domain'])


        domains = set(domains)
        for d in domains:
            if d.startswith('media'):
                rdb.sadd('/blacklist/host/socialmedia', d)
            else:
                # sonar.fkhi2-2.fna.whatsapp.net todo: what is this domain for?
                pass


try:
    block_fna_whatsapp_domains()
    fetch_invidious_instances()
    fetch_reddit_instances()
except Exception as e:
    print(e)

count = 0 
with io.StringIO() as s:
    s.write(prefix)
    for k in sorted(rdb.keys('/blacklist/host*')):
        c = rdb.scard(k)
        count += c
        s.write(f'\n# {k} - {c} entries\n\n')
        for m in sorted(rdb.smembers(k)):
            if m.endswith('.onion') or m.endswith('.i2p'):
                continue
            s.write(f'0.0.0.0 {m}\n')

    with open('/mnt/data/projects/hosts/hosts.txt', 'w') as f:
        f.write(s.getvalue().replace('$total_hosts', str(count)))



