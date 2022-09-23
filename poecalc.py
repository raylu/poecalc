#!/usr/bin/env python3

import sys
import gems
import stats

if len(sys.argv) == 3:
	import eventlet
	import eventlet.wsgi
	eventlet.monkey_patch()

# pylint: disable=wrong-import-position
import mimetypes

from pigwig import PigWig, Response
from pigwig.exceptions import HTTPException

import auras

curse_effect_selection = {
	'Enemy Type (optional)': 0,
	'None': 0,
	'Standard Boss': -33,
	'Guardian/Pinnacle': -66
}

def root(request):
	return Response.render(request, 'index.jinja2', {"enemy_types": curse_effect_selection.keys()})

def analyze_auras(request, account, character):
	# eventlet encodes PATH_INFO as latin1
	# https://github.com/eventlet/eventlet/blob/890f320b/eventlet/wsgi.py#L690
	# because PEP-0333 says so https://github.com/eventlet/eventlet/pull/497
	account = account.encode('latin1').decode('utf-8')
	character = character.encode('latin1').decode('utf-8')
	char_stats, char, skills = stats.fetch_stats(account, character)
	if 'aura_effect' in request.query and request.query['aura_effect'] != '':
		char_stats.aura_effect = int(request.query['aura_effect'])
	if 'enemy_type' in request.query:
		char_stats.more_hex_effect += curse_effect_selection[request.query['enemy_type']]

	active_skills = []
	for item in char['items']:
		active_skills += gems.parse_skills_in_item(item, char_stats)

	aura_results, vaal_aura_results = analyzer.analyze_auras(char_stats, char, active_skills, skills)
	curse_results = analyzer.analyze_curses(char_stats, active_skills)
	return Response.render(request, 'auras.jinja2', {
		'results': result_to_str(aura_results),
		'vaal_results': result_to_str(vaal_aura_results),
		'curse_results': result_to_str(curse_results),
		'aura_effect': request.query['aura_effect'],
		'account': account,
		'character': character,
		'enemy_types': curse_effect_selection.keys()
	})


def result_to_str(results: list[list[str]]) -> str:
	return '\n\n'.join('\n'.join(result) for result in results)

def static(request, path):
	content_type, _ = mimetypes.guess_type(path)
	try:
		with open('static/' + path, 'rb') as f:
			return Response(f.read(), content_type=content_type)
	except FileNotFoundError:
		raise HTTPException(404, '%r not found\n' % path) # pylint: disable=raise-missing-from

routes = [
	('GET', '/', root),
	('GET', '/auras/<account>/<character>', analyze_auras),
	('GET', '/static/<path:path>', static),
]

app = PigWig(routes, template_dir='templates')
analyzer = auras.Auras()

def main():
	if len(sys.argv) == 3:
		addr = sys.argv[1]
		port = int(sys.argv[2])
		eventlet.wsgi.server(eventlet.listen((addr, port)), app)
	else:
		app.main()

if __name__ == '__main__':
	main()
