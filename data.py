
import json

def load() -> tuple[dict[str, dict], dict[str, str]]:
	with open('../RePoE/RePoE/data/gems.json', 'rb') as f:
		raw_gems: dict[str, dict] = json.load(f)
	gems: dict[str, dict] = {}
	for k, v in raw_gems.items():
		if k.endswith('Royale') or v['base_item'] is None:
			continue
		gems[v['base_item']['display_name']] = v

	text: dict[str, str] = {}
	with open('../RePoE/RePoE/data/stat_translations/aura_skill.json', 'rb') as f:
		raw_text: list[dict] = json.load(f)
	for translation in raw_text:
		for k in translation['ids']:
			translated = translation['English'][0]
			if translated['string'].startswith('You and nearby '):
				text[k] = translated

	return gems, text
