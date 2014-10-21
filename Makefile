kafka_formation.template: kafka_formation.py cloud-init.sh node.json
	python $< > $@
