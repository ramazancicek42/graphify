"""
Cloud Resource Mapper for Graphify (AWS, GCP, Azure).

Extracts cloud infrastructure from:
- Terraform (.tf) files
- Kubernetes manifests (.yaml, .yml)
- CloudFormation templates (.json, .yaml)
- Docker Compose files
- Helm charts

Maps resources to code that uses them.
"""

import re
import os
import json
import yaml
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx


@dataclass
class CloudNode:
    """Represents a cloud resource."""
    name: str
    kind: str  # EC2, S3, LAMBDA, GKE, CLOUD_FUNCTION, etc.
    provider: str  # AWS, GCP, AZURE, K8S
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    resource_id: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)


class CloudResourceMapper:
    """Maps cloud infrastructure resources and their relationships."""
    
    def __init__(self):
        self.nodes: Dict[str, CloudNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []
        
    # ========== TERRAFORM PARSING ==========
    
    def parse_terraform(self, tf_dir: str) -> None:
        """Parse Terraform .tf files for resource definitions."""
        
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        data_pattern = r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        
        for root, dirs, files in os.walk(tf_dir):
            dirs[:] = [d for d in dirs if d not in {'.git', '.terraform'}]
            
            for file in files:
                if not file.endswith('.tf'):
                    continue
                    
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    lines = content.split('\n')
                    
                    # Find resources
                    for match in re.finditer(resource_pattern, content):
                        resource_type = match.group(1)
                        resource_name = match.group(2)
                        line_num = content[:match.start()].count('\n') + 1
                        
                        node_name = f"{resource_type}.{resource_name}"
                        
                        # Map Terraform type to cloud provider
                        provider, cloud_kind = self._map_tf_resource(resource_type)
                        
                        # Extract properties from block
                        props = self._extract_tf_block_properties(content, match.end())
                        
                        self.nodes[node_name] = CloudNode(
                            name=resource_name,
                            kind=cloud_kind,
                            provider=provider,
                            file_path=file_path,
                            line_number=line_num,
                            resource_id=node_name,
                            properties=props
                        )
                        
                    # Find data sources
                    for match in re.finditer(data_pattern, content):
                        data_type = match.group(1)
                        data_name = match.group(2)
                        line_num = content[:match.start()].count('\n') + 1
                        
                        node_name = f"data.{data_type}.{data_name}"
                        provider, cloud_kind = self._map_tf_resource(data_type)
                        
                        self.nodes[node_name] = CloudNode(
                            name=data_name,
                            kind=cloud_kind,
                            provider=provider,
                            file_path=file_path,
                            line_number=line_num,
                            resource_id=node_name,
                            properties={'source': 'data'}
                        )
                        
                    # Find references between resources
                    self._find_tf_references(content, file_path)
                    
                except Exception as e:
                    pass
                    
    def _map_tf_resource(self, tf_type: str) -> Tuple[str, str]:
        """Map Terraform resource type to provider and kind."""
        provider_map = {
            'aws_': 'AWS',
            'google_': 'GCP',
            'azurerm_': 'AZURE',
            'kubernetes_': 'K8S',
            'helm_': 'K8S',
            'docker_': 'DOCKER',
        }
        
        kind_map = {
            'aws_instance': 'EC2',
            'aws_s3_bucket': 'S3',
            'aws_lambda_function': 'LAMBDA',
            'aws_api_gateway_rest_api': 'API_GATEWAY',
            'aws_rds_cluster': 'RDS',
            'aws_dynamodb_table': 'DYNAMODB',
            'aws_sqs_queue': 'SQS',
            'aws_sns_topic': 'SNS',
            'aws_ecs_cluster': 'ECS',
            'aws_eks_cluster': 'EKS',
            'google_container_cluster': 'GKE',
            'google_cloudfunctions_function': 'CLOUD_FUNCTION',
            'google_storage_bucket': 'GCS',
            'google_pubsub_topic': 'PUBSUB',
            'azurerm_virtual_machine': 'VM',
            'azurerm_storage_account': 'STORAGE',
            'azurerm_function_app': 'FUNCTION_APP',
            'azurerm_service_bus_queue': 'SERVICE_BUS',
            'kubernetes_deployment': 'DEPLOYMENT',
            'kubernetes_service': 'SERVICE',
            'kubernetes_ingress': 'INGRESS',
        }
        
        provider = 'UNKNOWN'
        for prefix, prov in provider_map.items():
            if tf_type.startswith(prefix):
                provider = prov
                break
                
        kind = kind_map.get(tf_type, tf_type.upper().replace('_', '_'))
        
        return provider, kind
        
    def _extract_tf_block_properties(self, content: str, start_pos: int) -> Dict[str, Any]:
        """Extract properties from a Terraform block."""
        props = {}
        brace_count = 0
        started = False
        block_content = ""
        
        for char in content[start_pos:]:
            if char == '{':
                brace_count += 1
                started = True
            elif char == '}':
                brace_count -= 1
                if started and brace_count == 0:
                    break
            if started:
                block_content += char
                
        # Simple property extraction
        for match in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"([^"]*)"', block_content):
            props[match.group(1)] = match.group(2)
            
        return props
        
    def _find_tf_references(self, content: str, file_path: str) -> None:
        """Find references between Terraform resources."""
        # Look for ${aws_instance.web.id} style references
        ref_pattern = r'\$\{([a-zA-Z_][a-zA-Z0-9_.]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\}'
        
        for match in re.finditer(ref_pattern, content):
            resource_type = match.group(1)
            resource_name = match.group(2)
            attribute = match.group(3)
            
            source_node = f"{resource_type}.{resource_name}"
            
            # Find what resource contains this reference
            line_num = content[:match.start()].count('\n') + 1
            
            # This would need more context to determine the referencing resource
            # For now, we'll track it as a dependency
            self.edges.append((
                f"_ref_{line_num}",
                source_node,
                {'edge_type': 'references', 'attribute': attribute, 'file': file_path}
            ))
            
    # ========== KUBERNETES PARSING ==========
    
    def parse_kubernetes(self, k8s_dir: str) -> None:
        """Parse Kubernetes YAML manifests."""
        
        for root, dirs, files in os.walk(k8s_dir):
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules'}]
            
            for file in files:
                if not file.endswith(('.yaml', '.yml')):
                    continue
                    
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Parse multi-document YAML
                    docs = list(yaml.safe_load_all(content))
                    
                    for doc in docs:
                        if not doc:
                            continue
                            
                        kind = doc.get('kind', '')
                        metadata = doc.get('metadata', {})
                        name = metadata.get('name', 'unknown')
                        namespace = metadata.get('namespace', 'default')
                        
                        node_name = f"k8s.{namespace}.{kind}.{name}"
                        
                        # Map K8s kind to cloud kind
                        cloud_kind = kind.upper()
                        
                        # Extract spec properties
                        spec = doc.get('spec', {})
                        props = {
                            'namespace': namespace,
                            'labels': metadata.get('labels', {}),
                            'annotations': metadata.get('annotations', {}),
                        }
                        
                        # Add kind-specific properties
                        if kind == 'Deployment':
                            props['replicas'] = spec.get('replicas', 1)
                            template = spec.get('template', {})
                            container_spec = template.get('spec', {}).get('containers', [])
                            props['containers'] = [c.get('name') for c in container_spec]
                        elif kind == 'Service':
                            props['type'] = spec.get('type', 'ClusterIP')
                            props['ports'] = spec.get('ports', [])
                        elif kind == 'Ingress':
                            rules = spec.get('rules', [])
                            props['hosts'] = [r.get('host') for r in rules if r.get('host')]
                            
                        self.nodes[node_name] = CloudNode(
                            name=name,
                            kind=cloud_kind,
                            provider='K8S',
                            file_path=file_path,
                            resource_id=node_name,
                            properties=props
                        )
                        
                        # Find service selectors
                        if kind == 'Service':
                            selector = spec.get('selector', {})
                            for svc_name, label_value in selector.items():
                                # Try to find matching deployment/pod
                                for other_name, other_node in self.nodes.items():
                                    if other_node.properties.get('labels', {}).get(svc_name) == label_value:
                                        self.edges.append((
                                            node_name,
                                            other_name,
                                            {'edge_type': 'selects', 'file': file_path}
                                        ))
                                        
                except Exception as e:
                    pass
                    
    # ========== DOCKER COMPOSE PARSING ==========
    
    def parse_docker_compose(self, compose_dir: str) -> None:
        """Parse Docker Compose files."""
        
        for root, dirs, files in os.walk(compose_dir):
            for file in files:
                if not (file.startswith('docker-compose') and file.endswith('.yml')):
                    continue
                    
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        compose = yaml.safe_load(f)
                        
                    services = compose.get('services', {})
                    
                    for svc_name, svc_config in services.items():
                        node_name = f"docker.service.{svc_name}"
                        
                        props = {
                            'image': svc_config.get('image', ''),
                            'build': svc_config.get('build', ''),
                            'ports': svc_config.get('ports', []),
                            'environment': list(svc_config.get('environment', {}).keys()) if isinstance(svc_config.get('environment'), dict) else svc_config.get('environment', []),
                            'volumes': svc_config.get('volumes', []),
                        }
                        
                        self.nodes[node_name] = CloudNode(
                            name=svc_name,
                            kind='CONTAINER',
                            provider='DOCKER',
                            file_path=file_path,
                            properties=props
                        )
                        
                        # Find service dependencies
                        depends_on = svc_config.get('depends_on', [])
                        if isinstance(depends_on, dict):
                            depends_on = list(depends_on.keys())
                            
                        for dep in depends_on:
                            dep_node = f"docker.service.{dep}"
                            self.edges.append((
                                node_name,
                                dep_node,
                                {'edge_type': 'depends_on', 'file': file_path}
                            ))
                            
                except Exception:
                    pass
                    
    def link_code_to_cloud(self, code_dir: str) -> None:
        """Scan code for cloud SDK usage and link to resources."""
        
        sdk_patterns = {
            'aws': [
                r'boto3\.client\s*\(\s*[\'"]([^"\']+)[\'"]',
                r's3\.Client\s*\(',
                r'Lamdba\.invoke\s*\(\s*FunctionName\s*=\s*[\'"]([^"\']+)[\'"]',
                r'dynamodb\.Table\s*\(\s*[\'"]([^"\']+)[\'"]',
            ],
            'gcp': [
                r'google\.cloud\.(storage|bigquery|pubsub)\.Client',
                r'storage\.Client\s*\(\s*project\s*=\s*[\'"]([^"\']+)[\'"]',
            ],
            'azure': [
                r'BlobServiceClient\.from_connection_string',
                r'ComputeManagementClient\s*\(',
            ]
        }
        
        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__'}]
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                if ext not in ['.py', '.js', '.ts', '.java', '.go']:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for provider, patterns in sdk_patterns.items():
                        for pattern in patterns:
                            for match in re.finditer(pattern, content):
                                if match.lastindex:
                                    resource_ref = match.group(1)
                                    line_num = content[:match.start()].count('\n') + 1
                                    
                                    # Try to match with existing cloud nodes
                                    for node_name, node in self.nodes.items():
                                        if resource_ref.lower() in node.name.lower() or resource_ref.lower() in node_name.lower():
                                            self.edges.append((
                                                file_path,
                                                node_name,
                                                {
                                                    'edge_type': 'uses_cloud_resource',
                                                    'provider': provider,
                                                    'line': line_num
                                                }
                                            ))
                                            
                except Exception:
                    pass
                    
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed cloud resources."""
        G = nx.DiGraph()
        
        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                provider=node.provider,
                file=node.file_path,
                line=node.line_number,
                resource_id=node.resource_id,
                properties=node.properties,
                tags=node.tags,
                node_type='cloud_resource'
            )
            
        # Add edges
        for source, target, attrs in self.edges:
            if source in G.nodes and target in G.nodes:
                G.add_edge(source, target, **attrs)
            elif target in G.nodes:
                # Source might be a code file
                G.add_edge(source, target, **attrs)
                
        return G


def parse_cloud_resources(directory: str, providers: List[str] = ['terraform', 'kubernetes', 'docker']) -> nx.DiGraph:
    """Main entry point for cloud resource mapping."""
    mapper = CloudResourceMapper()
    
    if 'terraform' in providers:
        mapper.parse_terraform(directory)
        
    if 'kubernetes' in providers:
        mapper.parse_kubernetes(directory)
        
    if 'docker' in providers:
        mapper.parse_docker_compose(directory)
        
    # Link code to cloud resources
    mapper.link_code_to_cloud(directory)
    
    return mapper.build_graph()
