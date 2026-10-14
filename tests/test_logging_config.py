# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the logging configuration module."""

from __future__ import annotations

import logging
from pathlib import Path

from neuxelec import logging_config


def test_get_log_directory_exists():
    log_dir = logging_config.get_log_directory()
    assert isinstance(log_dir, Path)
    assert log_dir.exists()
    assert log_dir.is_dir()


def test_configure_logging_returns_log_file_and_is_idempotent():
    first = logging_config.configure_logging()
    assert isinstance(first, Path)
    assert first.name == "neuxelec.log"

    # Calling again must not add duplicate handlers or raise.
    handler_count = len(logging.getLogger().handlers)
    second = logging_config.configure_logging()
    assert second == first
    assert len(logging.getLogger().handlers) == handler_count


def test_logging_writes_to_file():
    log_file = logging_config.configure_logging()
    logger = logging.getLogger("neuxelec.tests")
    marker = "unit-test-marker-12345"
    logger.info(marker)

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert marker in log_file.read_text(encoding="utf-8")
