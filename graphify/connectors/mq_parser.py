"""
Message Queue Parser for Graphify (Kafka & RabbitMQ).

Extracts:
- Kafka Topics (producer/consumer relationships)
- RabbitMQ Exchanges, Queues, Bindings, Routing Keys
- Producer/Consumer code patterns
- Message schema references (Avro, Protobuf, JSON)
- Consumer groups and partition assignments
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx
import logging
logger = logging.getLogger(__name__)


@dataclass
class MQNode:
    """Represents a message queue element."""
    name: str
    kind: str  # TOPIC, EXCHANGE, QUEUE, BINDING, PRODUCER, CONSUMER
    broker_type: str  # KAFKA, RABBITMQ
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)


class MessageQueueParser:
    """Parses Kafka and RabbitMQ configurations and code."""

    def __init__(self):
        self.nodes: Dict[str, MQNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []

    # ========== KAFKA PARSING ==========

    def parse_kafka_topics_from_code(self, code_dir: str, languages: List[str] = ['python', 'java', 'javascript', 'typescript', 'go']) -> None:
        """Scan code for Kafka topic definitions and producer/consumer patterns."""

        kafka_patterns = {
            'python': {
                'topic_def': [
                    r'topic\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'KafkaTopic\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'["\']([a-zA-Z0-9_.-]+)["\']\s*:\s*\{?\s*["\']bootstrap_servers',
                ],
                'producer': [
                    r'KafkaProducer\s*\(',
                    r'\.send\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'produce\s*\(\s*topic\s*=\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer': [
                    r'KafkaConsumer\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'subscribe\s*\(\s*\[\s*[\'"]([^"\']+)[\'"]',
                    r'consume\s*\(\s*topics\s*=\s*\[([^\]]+)\]',
                ],
                'consumer_group': [
                    r'group_id\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'consumer_group\s*=\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'java': {
                'topic_def': [
                    r'String\s+TOPIC\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'@Topic\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'producer': [
                    r'new\s+KafkaProducer\s*<[^>]+>\s*\(',
                    r'producer\.send\s*\(\s*new\s+ProducerRecord\s*<>\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer': [
                    r'new\s+KafkaConsumer\s*<[^>]+>\s*\(',
                    r'consumer\.subscribe\s*\(\s*Collections\.singletonList\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer_group': [
                    r'props\.put\s*\(\s*ConsumerConfig\.GROUP_ID_CONFIG\s*,\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'javascript': {
                'topic_def': [
                    r'const\s+topic\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'topic:\s*[\'"]([^"\']+)[\'"]',
                ],
                'producer': [
                    r'new\s+KafkaProducer\s*\(',
                    r'\.send\s*\(\s*\{\s*topic:\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer': [
                    r'new\s+KafkaConsumer\s*\(',
                    r'\.subscribe\s*\(\s*\{\s*topics:\s*\[([^\]]+)\]',
                ]
            },
            'typescript': {
                'topic_def': [
                    r'const\s+topic:\s*string\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'@KafkaTopic\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'producer': [
                    r'client\.producer\s*\(\)\.send\s*\(\s*\{\s*topic:\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer': [
                    r'client\.consumer\s*\(\s*\{\s*groupId:\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'go': {
                'topic_def': [
                    r'var\s+topic\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'topic\s*:=\s*[\'"]([^"\']+)[\'"]',
                ],
                'producer': [
                    r'kafka\.NewWriter\s*\(\s*kafka\.WriterConfig\s*\{\s*Topic:\s*[\'"]([^"\']+)[\'"]',
                ],
                'consumer': [
                    r'kafka\.NewReader\s*\(\s*kafka\.ReaderConfig\s*\{\s*Topic:\s*[\'"]([^"\']+)[\'"]',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.java': 'java', '.js': 'javascript', '.ts': 'typescript', '.go': 'go'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    lines = content.split('\n')

                    # Find topics
                    for pattern in kafka_patterns.get(lang, {}).get('topic_def', []):
                        for match in re.finditer(pattern, content):
                            topic_name = match.group(1)
                            line_num = content[:match.start()].count('\n') + 1

                            if topic_name not in self.nodes:
                                self.nodes[topic_name] = MQNode(
                                    name=topic_name,
                                    kind='TOPIC',
                                    broker_type='KAFKA',
                                    file_path=file_path,
                                    line_number=line_num
                                )

                    # Find producers
                    for pattern in kafka_patterns.get(lang, {}).get('producer', []):
                        for match in re.finditer(pattern, content):
                            topic_name = match.group(1) if match.lastindex else None
                            if topic_name:
                                producer_node = f"_producer_{os.path.basename(file_path)}_{match.start()}"
                                if producer_node not in self.nodes:
                                    self.nodes[producer_node] = MQNode(
                                        name=producer_node,
                                        kind='PRODUCER',
                                        broker_type='KAFKA',
                                        file_path=file_path,
                                        line_number=content[:match.start()].count('\n') + 1,
                                        properties={'function': match.group(0)[:50]}
                                    )

                                self.edges.append((
                                    producer_node,
                                    topic_name,
                                    {'edge_type': 'produces_to', 'file': file_path}
                                ))

                    # Find consumers
                    for pattern in kafka_patterns.get(lang, {}).get('consumer', []):
                        for match in re.finditer(pattern, content):
                            topic_name = match.group(1) if match.lastindex else None
                            if topic_name:
                                consumer_node = f"_consumer_{os.path.basename(file_path)}_{match.start()}"
                                if consumer_node not in self.nodes:
                                    self.nodes[consumer_node] = MQNode(
                                        name=consumer_node,
                                        kind='CONSUMER',
                                        broker_type='KAFKA',
                                        file_path=file_path,
                                        line_number=content[:match.start()].count('\n') + 1
                                    )

                                self.edges.append((
                                    topic_name,
                                    consumer_node,
                                    {'edge_type': 'consumed_by', 'file': file_path}
                                ))

                    # Find consumer groups
                    for pattern in kafka_patterns.get(lang, {}).get('consumer_group', []):
                        for match in re.finditer(pattern, content):
                            group_id = match.group(1)
                            line_num = content[:match.start()].count('\n') + 1

                            group_node = f"_group_{group_id}"
                            if group_node not in self.nodes:
                                self.nodes[group_node] = MQNode(
                                    name=group_id,
                                    kind='CONSUMER_GROUP',
                                    broker_type='KAFKA',
                                    file_path=file_path,
                                    line_number=line_num
                                )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    # ========== RABBITMQ PARSING ==========

    def parse_rabbitmq_from_code(self, code_dir: str, languages: List[str] = ['python', 'java', 'javascript', 'typescript', 'go']) -> None:
        """Scan code for RabbitMQ exchanges, queues, and bindings."""

        rabbitmq_patterns = {
            'python': {
                'exchange': [
                    r'exchange_declare\s*\(\s*exchange\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'Exchange\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'channel\.exchange_declare\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'queue': [
                    r'queue_declare\s*\(\s*queue\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'Queue\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'channel\.queue_declare\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'binding': [
                    r'queue_bind\s*\(\s*queue\s*=\s*[\'"]([^"\']+)[\'"]\s*,\s*exchange\s*=\s*[\'"]([^"\']+)[\'"](?:\s*,\s*routing_key\s*=\s*[\'"]([^"\']+)[\'"])?',
                    r'bind\s*\(\s*exchange\s*=\s*[\'"]([^"\']+)[\'"]\s*,\s*routing_key\s*=\s*[\'"]([^"\']+)[\'"]',
                ],
                'publish': [
                    r'basic_publish\s*\(\s*exchange\s*=\s*[\'"]([^"\']+)[\'"]\s*,\s*routing_key\s*=\s*[\'"]([^"\']+)[\'"]',
                ],
                'consume': [
                    r'basic_consume\s*\(\s*queue\s*=\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'javascript': {
                'exchange': [
                    r'assertExchange\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'channel\.assertExchange\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'queue': [
                    r'assertQueue\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'channel\.assertQueue\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'binding': [
                    r'bindQueue\s*\(\s*[\'"]([^"\']+)[\'"]\s*,\s*[\'"]([^"\']+)[\'"]\s*,\s*[\'"]([^"\']+)[\'"]',
                ],
                'publish': [
                    r'publish\s*\(\s*[\'"]([^"\']+)[\'"]\s*,\s*[\'"]([^"\']+)[\'"]',
                ],
                'consume': [
                    r'consume\s*\(\s*[\'"]([^"\']+)[\'"]',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'javascript'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Find exchanges
                    for pattern in rabbitmq_patterns.get(lang, {}).get('exchange', []):
                        for match in re.finditer(pattern, content):
                            exchange_name = match.group(1)
                            line_num = content[:match.start()].count('\n') + 1

                            if exchange_name not in self.nodes:
                                self.nodes[exchange_name] = MQNode(
                                    name=exchange_name,
                                    kind='EXCHANGE',
                                    broker_type='RABBITMQ',
                                    file_path=file_path,
                                    line_number=line_num
                                )

                    # Find queues
                    for pattern in rabbitmq_patterns.get(lang, {}).get('queue', []):
                        for match in re.finditer(pattern, content):
                            queue_name = match.group(1)
                            line_num = content[:match.start()].count('\n') + 1

                            if queue_name not in self.nodes:
                                self.nodes[queue_name] = MQNode(
                                    name=queue_name,
                                    kind='QUEUE',
                                    broker_type='RABBITMQ',
                                    file_path=file_path,
                                    line_number=line_num
                                )

                    # Find bindings
                    for pattern in rabbitmq_patterns.get(lang, {}).get('binding', []):
                        for match in re.finditer(pattern, content):
                            if match.lastindex and match.lastindex >= 2:
                                queue_name = match.group(1)
                                exchange_name = match.group(2)
                                routing_key = match.group(3) if match.lastindex >= 3 else '#'

                                binding_name = f"{queue_name}_binds_{exchange_name}"

                                if binding_name not in self.nodes:
                                    self.nodes[binding_name] = MQNode(
                                        name=binding_name,
                                        kind='BINDING',
                                        broker_type='RABBITMQ',
                                        file_path=file_path,
                                        line_number=content[:match.start()].count('\n') + 1,
                                        properties={'routing_key': routing_key}
                                    )

                                self.edges.append((
                                    queue_name,
                                    exchange_name,
                                    {'edge_type': 'bound_to', 'routing_key': routing_key, 'file': file_path}
                                ))

                    # Find publishers
                    for pattern in rabbitmq_patterns.get(lang, {}).get('publish', []):
                        for match in re.finditer(pattern, content):
                            if match.lastindex and match.lastindex >= 2:
                                exchange_name = match.group(1)
                                routing_key = match.group(2)

                                publisher_node = f"_publisher_{os.path.basename(file_path)}_{match.start()}"
                                if publisher_node not in self.nodes:
                                    self.nodes[publisher_node] = MQNode(
                                        name=publisher_node,
                                        kind='PRODUCER',
                                        broker_type='RABBITMQ',
                                        file_path=file_path,
                                        line_number=content[:match.start()].count('\n') + 1
                                    )

                                self.edges.append((
                                    publisher_node,
                                    exchange_name,
                                    {'edge_type': 'publishes_to', 'routing_key': routing_key, 'file': file_path}
                                ))

                    # Find consumers
                    for pattern in rabbitmq_patterns.get(lang, {}).get('consume', []):
                        for match in re.finditer(pattern, content):
                            queue_name = match.group(1)

                            consumer_node = f"_consumer_{os.path.basename(file_path)}_{match.start()}"
                            if consumer_node not in self.nodes:
                                self.nodes[consumer_node] = MQNode(
                                    name=consumer_node,
                                    kind='CONSUMER',
                                    broker_type='RABBITMQ',
                                    file_path=file_path,
                                    line_number=content[:match.start()].count('\n') + 1
                                )

                                self.edges.append((
                                    queue_name,
                                    consumer_node,
                                    {'edge_type': 'consumed_by', 'file': file_path}
                                ))

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed MQ data."""
        G = nx.DiGraph()

        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                broker_type=node.broker_type,
                file=node.file_path,
                line=node.line_number,
                properties=node.properties,
                node_type='message_queue'
            )

        # Add edges
        for source, target, attrs in self.edges:
            if source in G.nodes and target in G.nodes:
                G.add_edge(source, target, **attrs)

        return G


def parse_mq_project(directory: str, brokers: List[str] = ['kafka', 'rabbitmq']) -> nx.DiGraph:
    """Main entry point for Message Queue parsing."""
    parser = MessageQueueParser()

    if 'kafka' in brokers:
        parser.parse_kafka_topics_from_code(directory)

    if 'rabbitmq' in brokers:
        parser.parse_rabbitmq_from_code(directory)

    return parser.build_graph()
