install:
	python -m pip install -e .

test:
	python -m unittest discover -v

lint:
	python -m compileall tiny_agents_md tests

doctor:
	python -m tiny_agents_md doctor .

agents:
	python -m tiny_agents_md loop .
