
import json

def load() -> dict[str, dict]:
	with open('../RePoE/RePoE/data/gems.json', 'rb') as f:
		raw_gems: dict[str, dict] = json.load(f)
		gems = {g['active_skill']['display_name']: g for g in raw_gems.values() if 'active_skill' in g}
	return gems
