
all: consul_formation.template

%.template: %.py cloud-init.sh node.json
	python $< > $@
