"""Robustness and unit tests for the full-stack connector parsers plus the
`graphify connectors` CLI subcommand.

Focused on the pieces the functional tests don't cover: malformed input, empty
corpora, and per-parser edge cases. Each parser must degrade gracefully (never
raise on a bad file) rather than crash the whole scan.

Runs with only the base deps graphify declares (networkx, PyYAML, pytest).
"""

import pytest

from graphify.connectors.graphql_parser import GraphQLParser
from graphify.connectors.grpc_parser import gRPCParser
from graphify.connectors.mq_parser import MessageQueueParser
from graphify.connectors.cloud_mapper import CloudResourceMapper


@pytest.mark.parametrize("extra", [[], ["--all"]])
def test_cli_connectors_subcommand(tmp_path, extra):
    import subprocess, sys, os, json
    (tmp_path / "svc.proto").write_text(
        'syntax = "proto3";\nmessage Empty {}\nservice Health { rpc Check (Empty) returns (Empty); }\n',
        encoding="utf-8",
    )
    (tmp_path / "producer.py").write_text('topic="t"\nKafkaConsumer("t")\n', encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  web:\n    image: nginx\n    depends_on:\n      - db\n  db:\n    image: postgres\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, "-m", "graphify", "connectors", str(tmp_path)] + extra
    env = dict(os.environ)
    env.pop("PYTHONWARNINGS", None)
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=repo_root())
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["cross_layer"]["api_endpoints"] >= 0
    if "--all" in extra:
        assert "message_queues" in report
        assert "grpc" in report
        assert "cloud" in report


def repo_root():
    import pathlib
    return str(pathlib.Path(__file__).resolve().parents[1])


class TestGraphQLParser:
    def test_empty_directory_no_crash(self, tmp_path):
        p = GraphQLParser()
        G = p.build_graph()
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_malformed_schema_no_crash(self, tmp_path):
        f = tmp_path / "bad.graphql"
        f.write_text("type Query {\n  this is not valid graphql !!\n  { unbalanced {{{{ \n", encoding="utf-8")
        p = GraphQLParser()
        p.parse_file(str(f))
        G = p.build_graph()
        assert isinstance(G, object)

    def test_enum_and_union_parsed(self, tmp_path):
        f = tmp_path / "s.graphql"
        f.write_text(
            'enum Role { ADMIN USER }\n'
            'union SearchResult = User\n'
            'type User implements Node { id: ID! }\n',
            encoding="utf-8",
        )
        p = GraphQLParser()
        p.parse_file(str(f))
        assert "Role" in p.nodes and p.nodes["Role"].kind == "ENUM"
        assert "SearchResult" in p.nodes and p.nodes["SearchResult"].kind == "UNION"


class TestgRPCParser:
    def test_empty_proto_no_crash(self):
        p = gRPCParser()
        assert p.build_graph().number_of_nodes() == 0

    def test_malformed_no_crash(self, tmp_path):
        f = tmp_path / "service.proto"
        f.write_text("syntax = proto3 garbage\nservice { {{ \n rpc (\n", encoding="utf-8")
        p = gRPCParser()
        p.parse_file(str(f))
        assert p.build_graph().number_of_nodes() >= 0

    def test_service_and_rpc_edges(self, tmp_path):
        f = tmp_path / "svc.proto"
        f.write_text(
            'syntax = "proto3";\n'
            'message Empty {}\n'
            "service Health {\n"
            "  rpc Check (Empty) returns (Empty);\n"
            "}\n",
            encoding="utf-8",
        )
        p = gRPCParser()
        p.parse_file(str(f))
        G = p.build_graph()
        assert "Health" in G.nodes
        assert any(
            e[2].get("edge_type") == "returns_response" for e in G.edges(data=True)
        )


class TestMessageQueueParser:
    def test_empty_dir_no_crash(self, tmp_path):
        p = MessageQueueParser()
        p.parse_kafka_topics_from_code(str(tmp_path), languages=["python", "go"])
        p.parse_rabbitmq_from_code(str(tmp_path))
        assert p.build_graph().number_of_nodes() == 0

    def test_kafka_producer_consumer_topics(self, tmp_path):
        code = tmp_path / "producer.py"
        code.write_text(
            'topic = "orders"\n'
            "producer = KafkaProducer(**conf)\n"
            "producer.send('orders', value=data)\n"
            "consumer = KafkaConsumer('orders')\n",
            encoding="utf-8",
        )
        p = MessageQueueParser()
        p.parse_kafka_topics_from_code(str(tmp_path), languages=["python"])
        G = p.build_graph()
        assert "orders" in G.nodes
        assert any(k.startswith("_producer_") for k in G.nodes)
        assert any(k.startswith("_consumer_") for k in G.nodes)


class TestCloudResourceMapper:
    def test_terraform_resources_and_refs(self, tmp_path):
        (tmp_path / "main.tf").write_text(
            'resource "aws_instance" "web" {\n'
            "  ami = \"ami-123\"\n"
            "}\n"
            'resource "aws_s3_bucket" "data" {}\n'
            "resource \"aws_security_group\" \"sg\" {\n"
            "  tags = {\n"
            '    Name = "${aws_instance.web.id}"\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        m = CloudResourceMapper()
        m.parse_terraform(str(tmp_path))
        G = m.build_graph()
        assert "aws_instance.web" in G.nodes
        assert G.nodes["aws_instance.web"]["provider"] in {"AWS", "EC2"}
        assert any(
            e[0] == "aws_instance.web" or e[1] == "aws_instance.web"
            for e in G.edges
        )

    def test_docker_compose_deps(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  web:\n"
            "    image: nginx\n"
            "    depends_on:\n"
            "      - db\n"
            "  db:\n"
            "    image: postgres\n",
            encoding="utf-8",
        )
        m = CloudResourceMapper()
        m.parse_docker_compose(str(tmp_path))
        G = m.build_graph()
        edges = [
            (u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "depends_on"
        ]
        assert ("docker.service.web", "docker.service.db") in edges

    def test_missing_pyyaml_degrades(self, monkeypatch):
        import graphify.connectors.cloud_mapper as cm
        monkeypatch.setattr(cm, "yaml", None)
        m = CloudResourceMapper()
        m.parse_kubernetes("/nonexistent")
        m.parse_docker_compose("/nonexistent")