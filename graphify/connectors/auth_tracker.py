"""
Authentication & Authorization Flow Tracker for Graphify.

Extracts:
- JWT token generation and validation points
- OAuth2 flows (authorization code, implicit, client credentials, password)
- Session management code
- Permission/role checks
- API key usage
- SSO integrations (SAML, OIDC)
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx
import logging
logger = logging.getLogger(__name__)


@dataclass
class AuthNode:
    """Represents an authentication/authorization element."""
    name: str
    kind: str  # JWT_ISSUER, JWT_VALIDATOR, OAUTH_ENDPOINT, SESSION_HANDLER, PERMISSION_CHECK, API_KEY
    auth_type: str  # JWT, OAUTH2, SESSION, API_KEY, SAML, OIDC
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    endpoint: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)


class AuthFlowTracker:
    """Tracks authentication and authorization flows in code."""

    def __init__(self):
        self.nodes: Dict[str, AuthNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []

    def parse_jwt_usage(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for JWT token generation and validation."""

        jwt_patterns = {
            'python': {
                'encode': [
                    r'jwt\.encode\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*[\'"]([^"\']+)[\'"]',
                    r'PyJWT\s*\.\s*encode',
                    r'create_access_token\s*\(\s*data\s*=\s*\{[^}]*["\']sub["\']:\s*[\'"]([^"\']+)[\'"]',
                ],
                'decode': [
                    r'jwt\.decode\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*algorithms\s*=\s*\[([^\]]+)\]',
                    r'verify_access_token\s*\(\s*token\s*:',
                    r'JWTBearer\s*\(',
                ],
                'claims': [
                    r'["\']exp["\']\s*:\s*([^,]+)',
                    r'["\']sub["\']\s*:\s*[\'"]([^"\']+)[\'"]',
                    r'["\']roles["\']\s*:\s*\[([^\]]+)\]',
                ]
            },
            'javascript': {
                'encode': [
                    r'jwt\.sign\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*\{\s*algorithm:\s*[\'"]([^"\']+)[\'"]',
                    r'jsonwebtoken\.sign',
                ],
                'decode': [
                    r'jwt\.verify\s*\(\s*([^,]+)\s*,\s*([^,]+)',
                    r'express\-jwt\s*\(\s*\{\s*secret:',
                ]
            },
            'typescript': {
                'encode': [
                    r'@nestjs/jwt\s*\.\s*JwtService\s*\.\s*sign',
                    r'jwt\.signAsync',
                ],
                'decode': [
                    r'@UseGuards\s*\(\s*JwtAuthGuard\s*\)',
                    r'@JwtAuth\s*\(\)',
                ]
            },
            'java': {
                'encode': [
                    r'JWT\.create\s*\(\)',
                    r'Jwts\.builder\s*\(\)',
                ],
                'decode': [
                    r'JWT\.require\s*\(\s*Algorithm\s*\.\s*([A-Z]+)',
                    r'Jwts\.parser\s*\(\)',
                ]
            },
            'go': {
                'encode': [
                    r'jwt\.NewWithClaims\s*\(\s*jwt\.SigningMethod([A-Z]+)',
                    r'token\.SignedString',
                ],
                'decode': [
                    r'jwt\.ParseWithClaims',
                    r'token\.Valid',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java', '.go': 'go'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Find JWT encode points (token issuers)
                    for pattern in jwt_patterns.get(lang, {}).get('encode', []):
                        for match in re.finditer(pattern, content):
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"jwt_issuer_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='JWT_ISSUER',
                                auth_type='JWT',
                                file_path=file_path,
                                line_number=line_num
                            )

                    # Find JWT decode points (token validators)
                    for pattern in jwt_patterns.get(lang, {}).get('decode', []):
                        for match in re.finditer(pattern, content):
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"jwt_validator_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='JWT_VALIDATOR',
                                auth_type='JWT',
                                file_path=file_path,
                                line_number=line_num
                            )

                    # Extract claims/roles from JWT
                    for pattern in jwt_patterns.get(lang, {}).get('claims', []):
                        for match in re.finditer(pattern, content):
                            if match.lastindex:
                                claim_value = match.group(1)

                                # Check if this is a role claim
                                if 'role' in match.group(0).lower():
                                    roles = [r.strip().strip('"\'') for r in claim_value.split(',')]

                                    role_node = f"jwt_roles_{match.start()}"
                                    self.nodes[role_node] = AuthNode(
                                        name=role_node,
                                        kind='ROLE_DEFINITION',
                                        auth_type='JWT',
                                        file_path=file_path,
                                        line_number=content[:match.start()].count('\n') + 1,
                                        roles=roles
                                    )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_oauth2_flows(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for OAuth2 endpoints and flows."""

        oauth_patterns = {
            'python': {
                'auth_endpoint': [
                    r'@app\.route\s*\(\s*[\'"](/oauth/authorize|/oauth/token|/login/oauth)[^"\']*["\']',
                    r'OAuth2PasswordBearer\s*\(\s*tokenUrl\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'AuthorizationCodeAuth\s*\(',
                ],
                'provider': [
                    r'GoogleOAuth2\s*\(\s*client_id\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'GitHubOAuth\s*\(\s*client_id',
                    r'register_oauth_client\s*\(\s*name\s*=\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'javascript': {
                'auth_endpoint': [
                    r'app\.get\s*\(\s*[\'"](/oauth/authorize|/oauth/callback)[^"\']*["\']',
                    r'passport\.use\s*\(\s*new\s+GoogleStrategy',
                ],
                'provider': [
                    r'clientId:\s*[\'"]([^"\']+)[\'"]',
                    r'clientSecret:\s*process\.env\.([A-Z_]+)',
                ]
            },
            'typescript': {
                'auth_endpoint': [
                    r'@Controller\s*\(\s*[\'"]oauth[\'"]',
                    r'@Get\s*\(\s*[\'"]auth/google[\'"]',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Find OAuth2 authorization endpoints
                    for pattern in oauth_patterns.get(lang, {}).get('auth_endpoint', []):
                        for match in re.finditer(pattern, content):
                            endpoint = match.group(1) if match.lastindex else '/oauth'
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"oauth_endpoint_{os.path.basename(file_path)}_{match.start()}"

                            # Determine flow type
                            flow_type = 'unknown'
                            if 'authorize' in endpoint.lower():
                                flow_type = 'authorization_code'
                            elif 'token' in endpoint.lower():
                                flow_type = 'token_exchange'
                            elif 'callback' in endpoint.lower() or 'callback' in endpoint.lower():
                                flow_type = 'callback'

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='OAUTH_ENDPOINT',
                                auth_type='OAUTH2',
                                file_path=file_path,
                                line_number=line_num,
                                endpoint=endpoint,
                                scopes=[flow_type]
                            )

                    # Find OAuth provider configurations
                    for pattern in oauth_patterns.get(lang, {}).get('provider', []):
                        for match in re.finditer(pattern, content):
                            provider_name = match.group(1) if match.lastindex else 'unknown'
                            line_num = content[:match.start()].count('\n') + 1

                            provider_node = f"oauth_provider_{provider_name}_{match.start()}"

                            self.nodes[provider_node] = AuthNode(
                                name=provider_node,
                                kind='OAUTH_PROVIDER',
                                auth_type='OAUTH2',
                                file_path=file_path,
                                line_number=line_num
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_session_management(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'php']) -> None:
        """Scan code for session handling."""

        session_patterns = {
            'python': {
                'session': [
                    r'session\s*\[\s*[\'"]user_id[\'"]\s*\]\s*=',
                    r'flask\.session\s*=',
                    r'SessionMiddleware',
                ],
                'cookie': [
                    r'set_cookie\s*\(\s*[\'"]session[\'"]',
                    r'@app\.before_request.*session',
                ]
            },
            'javascript': {
                'session': [
                    r'req\.session\.user\s*=',
                    r'express\-session\s*\(\s*\{',
                    r'Session\s*\(\s*\{\s*secret:',
                ]
            },
            'php': {
                'session': [
                    r'session_start\s*\(\s*\)',
                    r'$_SESSION\s*\[\s*[\'"]user[\'"]\s*\]',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.php': 'php'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern in session_patterns.get(lang, {}).get('session', []):
                        for match in re.finditer(pattern, content):
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"session_handler_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='SESSION_HANDLER',
                                auth_type='SESSION',
                                file_path=file_path,
                                line_number=line_num
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_permission_checks(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'csharp']) -> None:
        """Scan code for permission and role checks."""

        permission_patterns = {
            'python': {
                'check': [
                    r'@require_role\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@permission_required\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'if\s+not\s+user\.has_perm\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'user\.is_authenticated',
                    r'current_user\.role',
                ]
            },
            'javascript': {
                'check': [
                    r'can\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'authorize\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'user\.permissions\.includes',
                ]
            },
            'typescript': {
                'check': [
                    r'@Roles\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@Allow\s*\(\s*Roles\.([A-Z]+)',
                ]
            },
            'java': {
                'check': [
                    r'@PreAuthorize\s*\(\s*[\'"]hasRole\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@Secured\s*\(\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'csharp': {
                'check': [
                    r'\[Authorize\s*\(\s*Roles\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'User\.IsInRole\s*\(\s*[\'"]([^"\']+)[\'"]',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java', '.cs': 'csharp'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern in permission_patterns.get(lang, {}).get('check', []):
                        for match in re.finditer(pattern, content):
                            role_or_perm = match.group(1) if match.lastindex else 'authenticated'
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"auth_check_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='PERMISSION_CHECK',
                                auth_type='RBAC',
                                file_path=file_path,
                                line_number=line_num,
                                roles=[role_or_perm]
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_api_keys(self, code_dir: str) -> None:
        """Scan code for API key usage."""

        api_key_patterns = [
            r'X-API-Key',
            r'api_key\s*=\s*request\.headers',
            r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
            r'verify_api_key\s*\(',
            r'APIKeyHeader\s*\(',
        ]

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

                    for pattern in api_key_patterns:
                        for match in re.finditer(pattern, content, re.IGNORECASE):
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"api_key_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[node_name] = AuthNode(
                                name=node_name,
                                kind='API_KEY',
                                auth_type='API_KEY',
                                file_path=file_path,
                                line_number=line_num
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed auth flows."""
        G = nx.DiGraph()

        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                auth_type=node.auth_type,
                file=node.file_path,
                line=node.line_number,
                endpoint=node.endpoint,
                scopes=node.scopes,
                roles=node.roles,
                node_type='auth_flow'
            )

        # Add edges between related auth components
        self._add_auth_flow_edges(G)

        return G

    def _add_auth_flow_edges(self, G: nx.DiGraph) -> None:
        """Add edges connecting auth components into logical flows."""
        # Connect JWT issuers to validators in same file
        issuers = [(n, node) for n, node in self.nodes.items() if node.kind == 'JWT_ISSUER']
        validators = [(n, node) for n, node in self.nodes.items() if node.kind == 'JWT_VALIDATOR']

        for issuer_name, issuer_node in issuers:
            for validator_name, validator_node in validators:
                if issuer_node.file_path == validator_node.file_path:
                    G.add_edge(
                        issuer_name,
                        validator_name,
                        edge_type='jwt_flow',
                        file=issuer_node.file_path
                    )

        # Connect permission checks to their protected resources
        permission_nodes = [(n, node) for n, node in self.nodes.items() if node.kind == 'PERMISSION_CHECK']

        for perm_name, perm_node in permission_nodes:
            # This would ideally link to the actual route/handler being protected
            # For now, we mark it as a standalone check
            pass


def parse_auth_flows(directory: str) -> nx.DiGraph:
    """Main entry point for authentication flow parsing."""
    tracker = AuthFlowTracker()

    # Parse different auth mechanisms
    tracker.parse_jwt_usage(directory)
    tracker.parse_oauth2_flows(directory)
    tracker.parse_session_management(directory)
    tracker.parse_permission_checks(directory)
    tracker.parse_api_keys(directory)

    return tracker.build_graph()
