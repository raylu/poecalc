import math
import re
from copy import copy
from enum import Enum
from typing import Union
import data

all_gems, aura_translation, curse_translation = data.load()


class GemQualityType(Enum):
    Superior = 0
    Anomalous = 1
    Divergent = 2
    Phantasmal = 3


class Gem:
    name: str
    original_name: str
    level: int
    quality: int
    socket: int
    tags: set
    quality_type: GemQualityType

    def __init__(self, gem_dict: dict, socket: int) -> None:
        self.name = gem_dict['baseType']
        self.original_name = self.name
        self.level = 1
        self.quality = 0
        self.socket = socket
        gem_data = self.get_gem_data()
        self.tags = {gem_tag.lower() for gem_tag in
                     (gem_data['tags'] if gem_data['tags'] else [] + gem_data.get('types', []))}

        for prop in gem_dict['properties']:
            if prop['name'] == 'Level':
                self.level = int(re.search(r'(\d+)', prop['values'][0][0]).group(1))
            elif prop['name'] == 'Quality':
                self.quality = int(re.search(r'(\d+)', prop['values'][0][0]).group(1))

        self.quality_type = GemQualityType.Superior
        for quality_type in GemQualityType:
            if quality_type.name in gem_dict['typeLine']:
                self.quality_type = quality_type
                break

    def add_levels(self, level_mods: list[tuple[set[str], int]]) -> None:
        for required_tags, level in level_mods:
            if len(required_tags - self.tags) == 0:
                self.level += level

    def add_quality(self, quality_mods: list[tuple[set[str], int]]) -> None:
        for required_tags, quality in quality_mods:
            if len(required_tags - self.tags) == 0:
                self.quality += quality

    def iterate_effects(self, get_vaal_effect: bool = True) -> list[tuple[str, int]]:
        effects = []
        gem_data = self.get_gem_data(get_vaal_effect)
        for stat, value in zip(gem_data['static']['stats'], gem_data['per_level'][str(self.level)].get('stats', [])):
            if stat is None:  # catching some weird corrupted data (rage support)
                continue
            if value is None:
                value = stat.get('value')
            else:
                value = value.get('value')
            effects.append((stat['id'], value))
        effects.extend(self.quality_effect(get_vaal_effect))
        return effects

    def get_gem_data(self, get_vaal_effect: bool = True) -> dict:
        if self.name.startswith('Vaal') and not get_vaal_effect:
            return all_gems[self.original_name]
        return all_gems[self.name]

    def quality_effect(self, vaal_effect) -> list:
        return []

    def __repr__(self):
        attrs = ', '.join(f'{k}={repr(v)}' for k, v in self.__dict__.items())
        return f'{self.__class__.__name__}({attrs})'


class SupportGem(Gem):
    allowed_types: set
    excluded_types: set
    added_types: set
    support_gems_only: bool

    def __init__(self, gem_dict: dict, socket: int) -> None:
        super().__init__(gem_dict, socket)
        self.allowed_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem']['allowed_types']}
        self.excluded_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem']['excluded_types']}
        self.support_gems_only = self.get_gem_data()['support_gem']['supports_gems_only'] or (socket is None)
        self.added_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem'].get('added_types', [])}

    def can_support(self, active_skill_gem: Gem):
        if self.support_gems_only and active_skill_gem.socket is None:
            return False
        if self.allowed_types:
            if 'and' in self.allowed_types:
                if not all(allowed in active_skill_gem.tags for allowed in self.allowed_types if allowed != 'and'):
                    return False
            elif len(self.allowed_types & active_skill_gem.tags) == 0:
                return False
        return len(active_skill_gem.tags & self.excluded_types) == 0

    def quality_effect(self, vaal_effect) -> list:
        gem_data = self.get_gem_data()
        if not gem_data['static']['quality_stats']:
            return []
        quality_effect = gem_data['static']['quality_stats'][self.quality_type.value]
        return [(quality_effect['id'], int(quality_effect['value'] * self.quality / 1000))]


class SkillGem(Gem):
    aura_effect: int
    inc_curse_effect: int
    more_curse_effect: int
    more_hex_effect: int
    supports: list

    def __init__(self, gem_dict: dict, socket: int) -> None:
        super().__init__(gem_dict, socket)
        if 'hybrid' in gem_dict:
            self.original_name = gem_dict['hybrid']['baseTypeName']
        self.aura_effect = 0
        self.inc_curse_effect = 0
        self.more_curse_effect = 0
        self.more_hex_effect = 0
        self.supports = []
        self.tags |= {gem_type.lower() for gem_type in self.get_gem_data()['active_skill']['types']}
        self.tags.add(self.name.lower())

    def get_curse_effect(self):
        inc = 0
        more = 0
        if 'curse' in self.tags:
            inc += self.inc_curse_effect
            more += self.more_curse_effect
        if 'hex' in self.tags:
            more += self.more_hex_effect
        return round(((1 + inc / 100) * (1 + more / 100) - 1) * 100)

    def add_effects(self, character_stats) -> None:
        self.aura_effect += character_stats.aura_effect + character_stats.specific_aura_effect[self.name]
        self.inc_curse_effect += character_stats.inc_curse_effect + character_stats.specific_curse_effect[self.name]
        self.more_curse_effect += character_stats.more_curse_effect
        self.more_hex_effect += character_stats.more_hex_effect

    def quality_effect(self, vaal_effect) -> list:
        gem_data = self.get_gem_data(False)
        if not gem_data['static']['quality_stats']:
            return []
        # Vaal Skills always have the regular quality effect, even if they have alternative quality
        quality_type = GemQualityType.Superior if vaal_effect else self.quality_type

        quality_effect = gem_data['static']['quality_stats'][quality_type.value]
        quality_effect_value = int(quality_effect['value'] * self.quality / 1000)
        if quality_effect['id'] == 'aura_effect_+%':
            self.aura_effect += quality_effect_value
            return []
        if quality_effect['id'] == 'curse_effect_+%':
            self.inc_curse_effect += quality_effect_value
            return []
        return [(quality_effect['id'], quality_effect_value)]

    def applies_to_allies(self) -> bool:
        return 'aura' in self.tags and 'auraaffectsenemies' not in self.tags

    def apply_support(self, support_gem: SupportGem):
        if not support_gem.can_support(self):
            return
        self.tags |= support_gem.added_types
        has_effect = False
        for stat, value in support_gem.iterate_effects():
            if stat == 'non_curse_aura_effect_+%':
                self.aura_effect += value
            elif stat == 'aura_effect_+%':
                self.aura_effect += value
                self.inc_curse_effect += value  # Arrogance + Blasphemy
            elif stat in ['supported_aura_skill_gem_level_+', 'supported_active_skill_gem_level_+']:
                self.level += value
            elif stat == 'supported_active_skill_gem_quality_%':
                self.quality += value
            elif stat == 'curse_effect_+%':
                self.inc_curse_effect += value
            else:
                continue
            has_effect = True
        if has_effect:
            self.supports.append(support_gem)

    def get_aura(self, get_vaal_effect: bool) -> list[str]:
        aura_result = []
        previous_value = None
        for stat, value in self.iterate_effects(get_vaal_effect):
            formatted_text, previous_value = self.translate_effect(stat, value, previous_value, self.aura_effect,
                                                                   aura_translation)
            if not formatted_text:
                continue
            if m := re.search('you and nearby allies( deal| have| gain| are|) (.*)', formatted_text, re.IGNORECASE):
                aura_result.append(m.group(2))
            elif m := re.search("nearby allies' (.*)", formatted_text, re.IGNORECASE):
                aura_result.append(f'Your {m.group(1)}')
            elif formatted_text.startswith('Aura grants ') or formatted_text.startswith('Buff grants '):
                aura_result.append(formatted_text[len('Aura grants '):])
            elif not formatted_text.startswith('You and nearby Non-Minion Allies have a '):
                raise Exception(f'unhandled formatted line from {self.name}: {formatted_text}')

        if not aura_result:
            return []

        if self.supports:
            support_comment = '(' + ', '.join(f'{sup.name} {sup.level}' for sup in self.supports) + ')'
        else:
            support_comment = ''
        name = self.name
        if name.startswith('Vaal') and not get_vaal_effect:
            name = self.original_name
        special_quality = f'{self.quality_type.name} ' if self.quality_type != GemQualityType.Superior else ''
        header = f'// {special_quality}{name} (lvl {self.level}, {self.quality}%) {support_comment} {self.aura_effect}%'
        return [header] + aura_result

    def get_curse(self) -> list[str]:
        curse_result = []
        previous_value = None
        for stat, value in self.iterate_effects():
            formatted_text, previous_value = self.translate_effect(stat, value, previous_value, self.get_curse_effect(),
                                                                   curse_translation)
            if not formatted_text:
                continue
            if m := re.search(r'Other effects on Cursed enemies expire (\d+)% slower', formatted_text):
                # ailments are a subsection of "effects", but the only ones that matter
                # this would be inaccurate if there are other "more ailment duration" mods, but they are nonexistent
                curse_result.append(f'{m.group(1)}% more Duration of Ailments')
            elif 'Cursed Enemies are Debilitated' in formatted_text:
                # debilitate is not recognised by pob
                curse_result += ['Nearby Enemies deal 10% less damage', 'Nearby Enemies have 20% less movement speed.']
            elif 'to Hits against Cursed Enemies' in formatted_text:
                curse_result.append(formatted_text.replace('against Cursed Enemies', ''))
            elif m := re.search(r'Cursed enemies grant (\d+) (Life|Mana) when Hit by (Attacks|Spells)', formatted_text):
                curse_result.append(f'+{m.group(1)} {m.group(2)} gained for each Enemy hit by your {m.group(3)}')
            elif m := re.search(r'Cursed Enemies grant (.*)% (Life|Mana) Leech when Hit by (Attack|Spell)s',
                                formatted_text, re.IGNORECASE):
                curse_result.append(f'{m.group(1)}% of {m.group(3)} Damage leeched as {m.group(2)}')
            elif m := re.search(r'Cursed enemies grant (\d+) (Life|Mana) when Killed', formatted_text):
                curse_result.append(f'+{m.group(1)} {m.group(2)} gained on kill')
            elif m := re.search('Hits (against|on) Cursed Enemies have (.*)', formatted_text):
                curse_result.append(m.group(2))
            elif m := re.search('Ailments inflicted on Cursed Enemies (.*)', formatted_text):
                curse_result.append(f'Damaging Ailments {m.group(1)}')
            elif m := re.search(r'Cursed enemies take (\d+)% increased Damage from Damage over Time effects',
                                formatted_text):
                curse_result.append(f'Nearby Enemies have {m.group(1)}% increased Damage over Time taken')
            elif m := re.search(r'Cursed enemies take (\d+)% increased Damage from Projectile Hits', formatted_text):
                curse_result.append(f'Nearby Enemies take {m.group(1)}% increased Projectile Damage')
            elif m := re.search(r'(Ignite|Freeze|Shock)(|s) on Cursed enemies (have|has) (\d+)% increased Duration',
                                formatted_text):
                curse_result.append(f'{m.group(4)}% increased {m.group(1)} Duration on Enemies')
            elif 'increased Duration of Elemental Ailments on Cursed enemies' in formatted_text:
                curse_result.append(formatted_text.replace('on cursed Enemies', ''))
            elif m := re.search(r'Hits have (\d+)% chance to (.*) Cursed Enemies', formatted_text):
                curse_result.append(f'{m.group(1)}% Chance to {m.group(2)} Enemies on Hit')
            elif any(substr in formatted_text.lower() for substr in ['split', 'charge', 'overkill']):
                # not recognised by pob at all
                continue
            elif m := re.search('^Cursed(.*)Enemies (.*)', formatted_text, re.IGNORECASE):
                curse_result.append(f'Nearby Enemies {m.group(2)}')
            else:
                print(f'unhandled formatted line from {self.name}: {formatted_text}')

        if self.supports:
            support_comment = '(' + ', '.join(f'{sup.name} {sup.level}' for sup in self.supports) + ')'
        else:
            support_comment = ''
        name = self.name
        special_quality = f'{self.quality_type.name} ' if self.quality_type != GemQualityType.Superior else ''
        header = f'// {special_quality}{name} (lvl {self.level}, {self.quality}%) ' \
                 f'{support_comment} {self.get_curse_effect()}%'
        return [header] + curse_result

    @staticmethod
    def translate_effect(effect_id, effect_value, previous_effect_value, scaling_factor, translation_dict):
        """Finds the correct translation for an effect depending on the effects value"""
        if effect_id not in translation_dict:
            return '', None
        for translation in translation_dict[effect_id]:
            condition = translation['condition'][0]
            if condition == {} or condition.get('max', math.inf) >= effect_value >= condition.get('min', -math.inf):
                break
        else:
            if effect_value == 0:
                return '', None
            raise Exception(
                f'Could not find the right translation for '
                f'{effect_value} (value: {effect_value}) in {translation_dict[effect_id]}')
        value = scaled_value(effect_value, scaling_factor, translation['index_handlers'][0])
        if len(translation['format']) == 1:
            return translation['string'].format(value), None
        if previous_effect_value is not None:
            return translation['string'].format(previous_effect_value, value), None
        return '', value


def item_gem_dict(mod_string: str) -> dict:
    if m := re.match(r'Socketed Gems are Supported by Level (\d+) (.+)', mod_string):
        name = m.group(2) + ' Support'
        support = True
        level = m.group(1)
    elif m := re.match(r'Grants Level (\d+) (.+) Skill', mod_string):
        name = m.group(2)
        support = False
        level = m.group(1)
    elif m := re.match(r'Curse Enemies with (.*) (on|when) (.*) (\d+)% increased Effect', mod_string):
        name = m.group(1)
        support = False
        level = 1
    else:
        raise ValueError(f'Could not parse skill from mod: {mod_string}')

    return {'support': support, 'typeLine': name, 'baseType': name,
            'properties': [{'name': 'Level', 'values': [[str(level)]]}, {'name': 'Quality', 'values': [['+0%']]}]}


def scaled_value(value: int, factor: int, index_handlers: list[str]) -> Union[int, float]:
    allow_float = False
    for handler in index_handlers:
        if handler == 'per_minute_to_per_second':
            value /= 60
            allow_float = True
        elif handler == 'milliseconds_to_seconds_2dp':
            value /= 1000
            allow_float = True
        elif handler == 'negate':
            value *= -1
            continue
        elif handler == 'divide_by_one_hundred':
            value /= 100
            allow_float = True
        elif handler == 'per_minute_to_per_second_2dp':
            value /= 30
            allow_float = True
        else:
            raise Exception('unhandled index_handler: ' + handler)
    value *= 1 + factor / 100
    if allow_float:
        value = round(value, 1)
    else:
        value = int(value)
    return value


def parse_skills_in_item(item: dict, char_stats) -> list[SkillGem]:
    if item['inventoryId'] in ['Weapon2', 'Offhand2']:
        return []
    socketed_items = item.get('socketedItems', [])
    active_skills = [SkillGem(gem, socket=gem['socket']) for gem in socketed_items if not gem.get('support')]
    support_gems = [SupportGem(gem, socket=gem['socket']) for gem in socketed_items if gem.get('support')]
    level_mods = copy(char_stats.global_gem_level_increase)
    quality_mods = copy(char_stats.global_gem_quality_increase)
    for mod_type in ['explicitMods', 'implicitMods']:
        for mod in item.get(mod_type, []):
            if m := re.search(r'(.\d+) to Level of Socketed (.*)Gems', mod):
                level_mods += parse_gem_descriptor(m.group(2), int(m.group(1)))
            elif m := re.search(r'(.\d+)% to Quality of Socketed (.*)Gems', mod):
                quality_mods += parse_gem_descriptor(m.group(2), int(m.group(1)))
            elif 'Grants Level' in mod:
                active_skills.append(SkillGem(item_gem_dict(mod), socket=None))
            elif m := re.search(r'Curse Enemies with (.*) (on|when) (.*) (\d+)% increased Effect', mod):
                skill = SkillGem(item_gem_dict(mod), socket=None)
                skill.inc_curse_effect = int(m.group(4))
                active_skills.append(skill)
            elif 'Socketed Gems are Supported by Level' in mod:
                support_gems.append(SupportGem(item_gem_dict(mod), socket=None))

    for gem in support_gems + active_skills:
        if gem.socket is not None:
            gem.add_levels(level_mods)
            gem.add_quality(quality_mods)
    for skill in active_skills:
        skill.add_effects(char_stats)
        linked_sockets = []
        if skill.socket is not None:
            group = item['sockets'][skill.socket]['group']
            linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
        for support_gem in support_gems:
            if support_gem.socket is None or support_gem.socket in linked_sockets:
                skill.apply_support(support_gem)
    return active_skills


def parse_gem_descriptor(descriptor: Union[None, str], value: int) -> list[tuple[set, int]]:
    if descriptor is None:
        # since active skills and supports are mutually exclusive, we can increase both if no conditions are specified
        return [({'active_skill'}, value), ({'support'}, value)]
    descriptor = descriptor[:-1].lower()

    if 'non-' in descriptor:  # handles vaal caress - decreases all gem levels and then sets all vaal gems back to 0
        return [({'active_skill'}, value), ({'support'}, value), ({descriptor[4:]}, -value)]

    required_tags = set()
    if 'skill' in descriptor:
        required_tags.add('active_skill')
    if 'aoe' in descriptor:
        required_tags.add('area')

    all_tags = frozenset([
        'mark', 'strength', 'duration', 'link', 'critical', 'chaos', 'nova', 'spell', 'trigger', 'bow', 'attack',
        'slam', 'warcry', 'guard', 'channelling', 'travel', 'strike', 'blessing', 'low_max_level', 'intelligence',
        'cold', 'totem', 'projectile', 'orb', 'stance', 'brand', 'dexterity', 'physical', 'lightning', 'fire', 'aura',
        'melee', 'chaining', 'herald', 'mine', 'exceptional', 'minion', 'curse', 'hex', 'movement', 'vaal', 'support',
        'banner', 'golem', 'trap', 'blink', 'random_element', 'arcane'
    ])
    required_tags |= (all_tags & set(descriptor.split()))
    return [(required_tags, value)]
