'use strict';
(async () => {
	const form = document.querySelector('form#auras');
	form.addEventListener('submit', (event) => {
		event.preventDefault();
		const account = form.querySelector('input[name=account]').value;
		const character = form.querySelector('input[name=character]').value;
		const aura_effect = form.querySelector('input[name=aura_effect]').value;
		const enemy_type = form.querySelector('select[name=enemy_type]').value;
		window.location = `/auras/${account}/${character}?aura_effect=${aura_effect}&enemy_type=${enemy_type}`;
	});
})();
