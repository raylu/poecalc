'use strict';
(async () => {
	const form = document.querySelector('form#auras');
	form.addEventListener('submit', (event) => {
		event.preventDefault();
		const account = form.querySelector('input[name=account]').value;
		const character = form.querySelector('input[name=character]').value;
		window.location = `/auras/${account}/${character}`;
	});
})();
