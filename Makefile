.PHONY: build app run test install clean

build:
	swift build -c release

app:
	./scripts/build-app.sh release

run: app
	open build/VaultAI.app

test:
	swift test

install:
	./scripts/install.sh

clean:
	rm -rf .build build
