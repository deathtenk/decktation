VERSION := $(shell node scripts/release-version.mjs print)
TAG := v$(VERSION)

.PHONY: version version-check version-set release-check release-tag runtime-lock runtime-build

version:
	@node scripts/release-version.mjs print

version-check:
	@node scripts/release-version.mjs check

version-set:
	@test -n "$(VERSION)" || (echo "usage: make version-set VERSION=X.Y.Z" >&2; exit 1)
	@node scripts/release-version.mjs set "$(VERSION)"

release-check: version-check
	@set -eu; \
	if [ -x venv/bin/pytest ]; then venv/bin/pytest tests/ -q; \
	elif [ -x .venv/bin/pytest ]; then .venv/bin/pytest tests/ -q; \
	else python -m pytest tests/ -q; fi
	@python -m py_compile main.py runtime_client.py wow_voice_chat.py controller_listener.py deck_hid.py telemetry.py runtime/src/decktation_runtime/*.py

runtime-lock:
	@cd runtime && uv lock

runtime-build:
	@set -eu; \
	rm -rf backend/out; \
	image_tag="decktation-runtime-build:local"; \
	docker build --platform=linux/amd64 -t "$$image_tag" -f backend/Dockerfile .; \
	container_id="$$(docker create "$$image_tag")"; \
	trap 'docker rm -f "$$container_id" >/dev/null 2>&1 || true' EXIT; \
	docker start -a "$$container_id" >/dev/null; \
	docker cp "$$container_id:/backend/out" backend/; \
	docker rm -f "$$container_id" >/dev/null; \
	trap - EXIT

release-tag: release-check
	@set -eu; \
	test -z "$$(git status --porcelain)" || { \
		echo "error: commit or stash all changes before tagging" >&2; exit 1; \
	}; \
	! git rev-parse -q --verify "refs/tags/$(TAG)" >/dev/null || { \
		echo "error: tag $(TAG) already exists" >&2; exit 1; \
	}; \
	git tag -a "$(TAG)" -m "Release $(TAG)"; \
	echo "Created $(TAG). Push it with: git push origin $(TAG)"
