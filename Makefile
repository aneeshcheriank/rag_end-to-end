VENV = .venv/bin

# normal development ci/cd
install:
	$(VENV)/pip install -r requirements.txt

# when requriements changes in requriements.in
compile:
	$(VENV)/pip-compile requirements.in

# updating packages to a newer version
upgrade:
	$(VENV)/pip-compile --upgrade requirements.in

