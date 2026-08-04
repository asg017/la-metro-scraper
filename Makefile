PKG = src/la_metro_scraper

all: $(PKG)/_queries.py

$(PKG)/_queries.py: $(PKG)/procedures.sql $(PKG)/schema.sql tools/codegen.py
	cd $(PKG) && uv run solite codegen procedures.sql --schema schema.sql | uv run python ../../tools/codegen.py > _queries.py
