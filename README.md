# PoE calculator (currently only for auras)

live version: https://poecalc.fly.dev

## setup

1.
```sh
mkdir data
cd data
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/gems.json
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/stat_translations/aura_skill.json
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/stat_translations/curse_skill.json
wget https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/src/Data/LegionPassives.lua
mkdir TimelessJewels
cd TimelessJewels
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/glorious_vanity.zip
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/glorious_vanity_passives.txt
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/brutal_restraint.zip
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/brutal_restraint_passives.txt
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/elegant_hubris.zip
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/elegant_hubris_passives.txt
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/militant_faith.zip
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/militant_faith_passives.txt
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/lethal_pride.zip
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/lethal_pride_passives.txt
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/stats.txt
```
2. `pip3 install -r requirements.txt`
3. `./poecalc.py`
