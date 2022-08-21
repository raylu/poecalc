#!/usr/bin/env python3

import data
import stats

def analyze(account, character_name):
	gems = data.load()
	char_stats, character = stats.fetch_stats(account, character_name)
	print(char_stats)

	for gem_name, level, supports in iter_gems(character['items']):
		print(gem_name, level, supports)
		gems[gem_name]

def iter_gems(items):
	for item in items:
		#from pprint import pprint; pprint(item)
		for gem in item.get('socketedItems', []):
			if gem['support']:
				continue
			name, level = parse_gem(gem)
			supports = list(iter_supports(item, gem['socket']))
			yield name, level, supports

def parse_gem(gem):
	if 'hybrid' in gem:
		name = gem['hybrid']['baseTypeName']
	else:
		name = gem['baseType']

	level = None
	for prop in gem['properties']:
		if prop['name'] == 'Level' and prop['type'] == 5:
			level = int(prop['values'][0][0])
			break
	assert level is not None, "couldn't get level for " + gem['typeLine']

	return name, level

def iter_supports(item: dict, socket_idx: int):
	group = item['sockets'][socket_idx]['group']
	linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
	for gem in item['socketedItems']:
		if gem['support'] and gem['socket'] in linked_sockets:
			yield parse_gem(gem)

if __name__ == '__main__':
	analyze('raylu', 'auraraylu')
