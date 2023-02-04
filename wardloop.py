import stats

def analyze(account: str, character_name: str) -> None:
	char_stats, _, _ = stats.fetch_stats(account, character_name)
	print(char_stats)

if __name__ == '__main__':
	analyze('raylu', 'rayluloop')
