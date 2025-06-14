# HEMS Data Collector Makefile

.PHONY: install update uninstall status help

help:
	@echo "HEMS Data Collector Management Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install   - Install the service"
	@echo "  make update    - Update the service"
	@echo "  make uninstall - Uninstall the service"
	@echo "  make status    - Display service status"
	@echo "  make help      - Display this help message"

install:
	sudo ./service-manager.sh install

update:
	sudo ./service-manager.sh update

uninstall:
	sudo ./service-manager.sh uninstall

status:
	sudo ./service-manager.sh status
