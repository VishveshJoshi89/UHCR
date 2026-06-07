import pytest
import argparse
from uhcr.cli import _build_parser

def test_cli_parser_analytics():
    parser = _build_parser()
    args = parser.parse_args(["analytics", "job-123"])
    assert args.subcommand == "analytics"
    assert args.job_id == "job-123"
    assert args.compare is None
    
def test_cli_parser_analytics_compare():
    parser = _build_parser()
    args = parser.parse_args(["analytics", "job-123", "--compare", "job-456"])
    assert args.subcommand == "analytics"
    assert args.job_id == "job-123"
    assert args.compare == "job-456"

def test_cli_parser_serve():
    parser = _build_parser()
    args = parser.parse_args(["serve", "--http-port", "9000", "--workers", "8"])
    assert args.subcommand == "serve"
    assert args.http_port == 9000
    assert args.workers == 8

def test_cli_parser_monitor():
    parser = _build_parser()
    args = parser.parse_args(["monitor", "--interval", "5", "--json"])
    assert args.subcommand == "monitor"
    assert args.interval == 5
    assert args.as_json is True
