"""
Experimento 1: Detección de Ataques Man-in-the-Middle (MITM)

Este script simula un número configurable de requests, donde un porcentaje
específico genera ataques MITM para validar que el sistema detecta correctamente
las inconsistencias de IP en contexto de autenticación.

Uso:
    python experiment_1_mitm_detection.py --total-requests 100 --mitm-percentage 30
    python experiment_1_mitm_detection.py --total-requests 300 --mitm-percentage 50
"""

import requests
import argparse
import json
import time
import random
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('experiment_1_results.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MITMExperiment:
    """Gestor del experimento de detección MITM"""
    
    def __init__(self, api_gateway_url: str, total_requests: int, mitm_percentage: float, num_tokens: int = 5):
        """
        Inicializa el experimento
        
        Args:
            api_gateway_url: URL base del API Gateway (ej: http://localhost:5000)
            total_requests: Número total de requests a realizar
            mitm_percentage: Porcentaje de requests que simularán ataques MITM (0-100)
            num_tokens: Número de tokens independientes a obtener del usuario admin
        """
        self.api_gateway_url = api_gateway_url.rstrip('/')
        self.total_requests = total_requests
        self.mitm_percentage = mitm_percentage
        self.num_tokens = num_tokens
        
        # Validar parámetros
        if not 0 <= mitm_percentage <= 100:
            raise ValueError("mitm_percentage debe estar entre 0 y 100")
        
        self.legitimate_requests = int(total_requests * (100 - mitm_percentage) / 100)
        self.mitm_requests = total_requests - self.legitimate_requests
        
        # IP original de autenticación
        self.original_ip = "127.0.0.1"
        
        # IPs atacantes potenciales (simular diferentes orígenes)
        self.attacker_ips = [
            "192.168.1.100",
            "192.168.1.101",
            "10.0.0.50",
            "10.0.0.51",
            "203.0.113.42",  # Ejemplo de IP externa
        ]
        
        # Credenciales del único usuario disponible
        self.client_id = "admin"
        self.client_secret = "admin"
        
        # Pool de tokens independientes
        self.tokens = []
        self.token_index = 0
        
        # Resultados del experimento
        self.results = {
            'legitimate_requests': [],
            'mitm_requests': [],
            'statistics': {}
        }
    
    def authenticate_token_pool(self) -> bool:
        """
        Obtiene múltiples tokens JWT independientes del usuario admin
        Cada token tiene su propio ciclo de vida de blacklist
        
        Returns:
            bool: True si se obtuvieron suficientes tokens, False en caso contrario
        """
        logger.info("="*80)
        logger.info("FASE 1: OBTENCIÓN DE POOL DE TOKENS INDEPENDIENTES")
        logger.info("="*80)
        
        auth_url = f"{self.api_gateway_url}/token"
        
        for i in range(self.num_tokens):
            try:
                logger.info(f"Obteniendo token {i+1}/{self.num_tokens} para usuario: {self.client_id}")
                
                response = requests.post(
                    auth_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret
                    },
                    headers={
                        "X-Forwarded-For": self.original_ip
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get('access_token')
                    self.tokens.append(token)
                    logger.info(f"Token {i+1} obtenido: {token[:50]}...")
                else:
                    logger.error(f"Error obteniendo token {i+1}: {response.status_code}")
                    logger.error(f"  Respuesta: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Excepción obteniendo token {i+1}: {str(e)}")
                return False
            
            # Pequeño delay entre obtenciones para asegurar tokens diferentes
            time.sleep(0.2)
        
        logger.info(f"\nPool de tokens obtenido: {len(self.tokens)} tokens independientes\n")
        return len(self.tokens) > 0
    
    def get_next_token(self) -> str:
        """
        Obtiene el siguiente token del pool (round-robin)
        Si el pool se agota, obtiene uno nuevo dinámicamente
        
        Returns:
            str: Token JWT
        """
        if self.token_index >= len(self.tokens):
            # Pool agotado, obtener nuevo token dinámicamente
            logger.debug("Pool de tokens agotado, obteniendo nuevo token dinámicamente...")
            if self.get_new_token():
                self.token_index = len(self.tokens) - 1
            else:
                logger.warning("No se pudo obtener nuevo token dinámicamente")
                return None
        
        token = self.tokens[self.token_index]
        self.token_index += 1
        return token
    
    def get_new_token(self) -> bool:
        """
        Obtiene un nuevo token dinámicamente
        
        Returns:
            bool: True si se obtuvo exitosamente, False en caso contrario
        """
        auth_url = f"{self.api_gateway_url}/token"
        
        try:
            response = requests.post(
                auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={
                    "X-Forwarded-For": self.original_ip
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                self.tokens.append(token)
                logger.debug(f"Nuevo token obtenido dinámicamente: {token[:50]}...")
                return True
            else:
                logger.warning(f"Error obteniendo token dinámicamente: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Excepción obteniendo token dinámicamente: {str(e)}")
            return False
    
    def make_legitimate_request(self, request_number: int) -> Dict:
        """
        Realiza una request legítima desde la IP original
        
        Args:
            request_number: Número de secuencia de la request
            
        Returns:
            Dict con resultado de la request
        """
        token = self.get_next_token()
        historico_url = f"{self.api_gateway_url}/historico"
        
        try:
            response = requests.post(
                historico_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Forwarded-For": self.original_ip
                },
                json={},
                timeout=5
            )
            
            result = {
                'request_number': request_number,
                'type': 'LEGITIMATE',
                'client_ip': self.original_ip,
                'status_code': response.status_code,
                'timestamp': datetime.now().isoformat(),
                'success': response.status_code == 200,
                'response_time': response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                result['mitm_detected'] = False
            else:
                try:
                    data = response.json()
                    result['mitm_detected'] = data.get('mitm_detected', False)
                    result['error'] = data.get('error', 'Unknown error')
                except:
                    result['mitm_detected'] = False
                    result['error'] = response.text[:100]
            
            status_text = "Success" if result['success'] else "Failed"
            logger.debug(
                f"  [{status_text}] [{request_number}] LEGITIMATE | "
                f"IP: {self.original_ip} | Status: {response.status_code} | "
                f"Time: {result['response_time']:.3f}s"
            )
            
            return result
            
        except Exception as e:
            logger.debug(f"  [Failed] [{request_number}] LEGITIMATE | Exception: {str(e)}")
            return {
                'request_number': request_number,
                'type': 'LEGITIMATE',
                'client_ip': self.original_ip,
                'status_code': 0,
                'success': False,
                'error': str(e),
                'mitm_detected': False,
                'timestamp': datetime.now().isoformat(),
                'response_time': 0
            }
    
    def make_mitm_request(self, request_number: int) -> Dict:
        """
        Realiza una request simulando un ataque MITM (desde una IP diferente)
        CADA ataque MITM obtiene un token NUEVO que será invalidado después
        
        Args:
            request_number: Número de secuencia de la request
            
        Returns:
            Dict con resultado de la request
        """
        # Obtener un token NUEVO para el ataque (será invalidado después)
        if not self.get_new_token():
            logger.warning(f"No se pudo obtener token para ataque MITM #{request_number}")
            return {
                'request_number': request_number,
                'type': 'MITM_ATTACK',
                'original_ip': self.original_ip,
                'attacker_ip': 'unknown',
                'status_code': 0,
                'success': False,
                'error': 'No se pudo obtener token',
                'mitm_detected': False,
                'detection_result': 'ERROR',
                'timestamp': datetime.now().isoformat(),
                'response_time': 0
            }
        
        # Usar el último token obtenido
        token = self.tokens[-1]
        historico_url = f"{self.api_gateway_url}/historico"
        attacker_ip = random.choice(self.attacker_ips)
        
        try:
            response = requests.post(
                historico_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Forwarded-For": attacker_ip
                },
                json={},
                timeout=5
            )
            
            result = {
                'request_number': request_number,
                'type': 'MITM_ATTACK',
                'original_ip': self.original_ip,
                'attacker_ip': attacker_ip,
                'status_code': response.status_code,
                'timestamp': datetime.now().isoformat(),
                'success': response.status_code == 200,
                'response_time': response.elapsed.total_seconds()
            }
            
            # Esperamos que el servidor detecte MITM (status code != 200)
            if response.status_code == 200:
                result['mitm_detected'] = False
                result['detection_result'] = 'NOT_DETECTED'  # ✗ Error: No se detectó el ataque
            else:
                try:
                    data = response.json()
                    result['mitm_detected'] = data.get('mitm_detected', False)
                    result['error'] = data.get('error', 'Unknown error')
                    result['detection_result'] = 'CORRECTLY_DETECTED' if data.get('mitm_detected') else 'FALSE_NEGATIVE'
                except:
                    result['mitm_detected'] = False
                    result['error'] = response.text[:100]
                    result['detection_result'] = 'UNABLE_TO_PARSE'
            
            status_text = "Protected" if result['mitm_detected'] else "Warning"
            logger.debug(
                f"  [{status_text}] [{request_number}] MITM_ATTACK | "
                f"Original: {self.original_ip} | Attacker: {attacker_ip} | "
                f"Status: {response.status_code} | Detected: {result['mitm_detected']}"
            )
            
            return result
            
        except Exception as e:
            logger.debug(f"  [Warning] [{request_number}] MITM_ATTACK | Exception: {str(e)}")
            return {
                'request_number': request_number,
                'type': 'MITM_ATTACK',
                'original_ip': self.original_ip,
                'attacker_ip': attacker_ip,
                'status_code': 0,
                'success': False,
                'error': str(e),
                'mitm_detected': False,
                'detection_result': 'ERROR',
                'timestamp': datetime.now().isoformat(),
                'response_time': 0
            }
    
    def run(self):
        """Ejecuta el experimento completo"""
        logger.info("\n")
        logger.info("=" * 80)
        logger.info(f"EXPERIMENTO 1: DETECCIÓN DE ATAQUES MITM".center(80))
        logger.info("=" * 80)
        logger.info(f"\nParámetros:")
        logger.info(f"  • Total de requests: {self.total_requests}")
        logger.info(f"  • Requests legítimas: {self.legitimate_requests}")
        logger.info(f"  • Ataques MITM: {self.mitm_requests}")
        logger.info(f"  • Porcentaje MITM: {self.mitm_percentage}%")
        logger.info(f"  • URL API Gateway: {self.api_gateway_url}")
        logger.info(f"  • IP Original: {self.original_ip}")
        logger.info(f"  • Tokens independientes: {self.num_tokens}")
        logger.info(f"\nEjecución: TODAS las requests legítimas primero, luego TODOS los ataques MITM")
        logger.info(f"(Esto asegura que los MITM no interfieran con sesiones legítimas)")
        
        # Paso 1: Obtener pool de tokens independientes
        if not self.authenticate_token_pool():
            logger.error("No se pudieron obtener tokens. Experimento abortado.")
            return False
        
        # Paso 2: Realizar TODAS las requests legítimas primero
        logger.info("\n" + "="*80)
        logger.info("FASE 2A: EJECUCIÓN DE REQUESTS LEGÍTIMAS")
        logger.info("="*80)
        
        start_time = time.time()
        
        for idx in range(1, self.legitimate_requests + 1):
            result = self.make_legitimate_request(idx)
            self.results['legitimate_requests'].append(result)
            
            # Mostrar progreso cada 10 requests
            if idx % 10 == 0:
                logger.info(f"Progreso: {idx}/{self.legitimate_requests} requests legítimas ...")
            
            # Pequeño delay para evitar sobrecargar el servidor
            time.sleep(0.1)
        
        logger.info(f"Completadas todas las {self.legitimate_requests} requests legítimas")
        
        # Paso 3: Realizar TODOS los ataques MITM después
        logger.info("\n" + "="*80)
        logger.info("FASE 2B: EJECUCIÓN DE ATAQUES MITM")
        logger.info("="*80)
        
        for idx in range(self.legitimate_requests + 1, self.total_requests + 1):
            result = self.make_mitm_request(idx)
            self.results['mitm_requests'].append(result)
            
            # Mostrar progreso cada 10 requests
            if (idx - self.legitimate_requests) % 10 == 0:
                logger.info(f"Progreso: {idx - self.legitimate_requests}/{self.mitm_requests} ataques MITM ...")
            
            # Pequeño delay
            time.sleep(0.1)
        
        execution_time = time.time() - start_time
        logger.info(f"Completados todos los {self.mitm_requests} ataques MITM")
        
        # Paso 4: Calcular estadísticas
        logger.info("\n" + "="*80)
        logger.info("FASE 3: ANÁLISIS DE RESULTADOS")
        logger.info("="*80)
        
        self._calculate_statistics(execution_time)
        self._generate_report()
        
        return True
    
    def _calculate_statistics(self, execution_time: float):
        """Calcula estadísticas del experimento"""
        stats = {
            'total_requests': self.total_requests,
            'execution_time': execution_time,
            'requests_per_second': self.total_requests / execution_time if execution_time > 0 else 0,
            'legitimate': {},
            'mitm': {},
            'overall': {}
        }
        
        # Estadísticas de requests legítimas
        if self.results['legitimate_requests']:
            legit = self.results['legitimate_requests']
            stats['legitimate'] = {
                'total': len(legit),
                'successful': sum(1 for r in legit if r['success']),
                'failed': sum(1 for r in legit if not r['success']),
                'average_response_time': sum(r['response_time'] for r in legit) / len(legit),
                'false_positives': sum(1 for r in legit if r.get('mitm_detected', False)),  # Mal detectadas como MITM
            }
            success_rate = (stats['legitimate']['successful'] / stats['legitimate']['total'] * 100) if stats['legitimate']['total'] > 0 else 0
            stats['legitimate']['success_rate'] = success_rate
        
        # Estadísticas de ataques MITM
        if self.results['mitm_requests']:
            mitm = self.results['mitm_requests']
            stats['mitm'] = {
                'total': len(mitm),
                'correctly_detected': sum(1 for r in mitm if r.get('mitm_detected', False)),
                'not_detected': sum(1 for r in mitm if not r.get('mitm_detected', False)),
                'errors': sum(1 for r in mitm if r.get('detection_result') == 'ERROR'),
                'average_response_time': sum(r['response_time'] for r in mitm) / len(mitm),
            }
            detection_rate = (stats['mitm']['correctly_detected'] / stats['mitm']['total'] * 100) if stats['mitm']['total'] > 0 else 0
            stats['mitm']['detection_rate'] = detection_rate
        
        # Estadísticas generales
        all_requests = self.results['legitimate_requests'] + self.results['mitm_requests']
        stats['overall'] = {
            'total_successful': sum(1 for r in all_requests if r['success']),
            'total_failed': sum(1 for r in all_requests if not r['success']),
            'average_response_time': sum(r['response_time'] for r in all_requests) / len(all_requests) if all_requests else 0,
        }
        
        self.results['statistics'] = stats
    
    def _generate_report(self):
        """Genera reporte detallado del experimento"""
        stats = self.results['statistics']
        
        # Resumen general
        logger.info("\nRESUMEN DEL EXPERIMENTO")
        logger.info("-" * 80)
        logger.info(f"Tiempo de ejecución: {stats['execution_time']:.2f}s")
        logger.info(f"Requests por segundo: {stats['requests_per_second']:.2f} req/s")
        
        # Resultados de requests legítimas
        if stats['legitimate']:
            logger.info("\nREQUESTS LEGÍTIMAS:")
            logger.info(f"  Total: {stats['legitimate']['total']}")
            logger.info(f"  Exitosas: {stats['legitimate']['successful']} ({stats['legitimate']['success_rate']:.1f}%)")
            logger.info(f"  Fallidas: {stats['legitimate']['failed']}")
            logger.info(f"  Falsos positivos (detectadas como MITM): {stats['legitimate']['false_positives']}")
            logger.info(f"  Tiempo de respuesta promedio: {stats['legitimate']['average_response_time']:.3f}s")
        
        # Resultados de ataques MITM
        if stats['mitm']:
            logger.info("\nATAQUES MITM:")
            logger.info(f"  Total: {stats['mitm']['total']}")
            logger.info(f"  Detectados correctamente: {stats['mitm']['correctly_detected']} ({stats['mitm']['detection_rate']:.1f}%)")
            logger.info(f"  No detectados: {stats['mitm']['not_detected']}")
            logger.info(f"  Errores: {stats['mitm']['errors']}")
            logger.info(f"  Tiempo de respuesta promedio: {stats['mitm']['average_response_time']:.3f}s")
        
        # Resultados generales
        logger.info("\nESTADÍSTICAS GENERALES:")
        logger.info(f"  Total de requests exitosas: {stats['overall']['total_successful']}")
        logger.info(f"  Total de requests fallidas: {stats['overall']['total_failed']}")
        logger.info(f"  Tiempo de respuesta promedio: {stats['overall']['average_response_time']:.3f}s")
        
        # Evaluación de hipótesis
        logger.info("\n" + "="*80)
        logger.info("EVALUACIÓN DE HIPÓTESIS")
        logger.info("="*80)
        
        if stats['mitm']:
            detection_rate = stats['mitm']['detection_rate']
            if detection_rate == 100:
                logger.info("HIPOTESIS CONFIRMADA: El sistema detecta el 100% de ataques MITM")
            elif detection_rate >= 95:
                logger.info(f"HIPOTESIS PARCIALMENTE CONFIRMADA: Tasa de detección {detection_rate:.1f}%")
            else:
                logger.info(f"HIPOTESIS RECHAZADA: Tasa de detección {detection_rate:.1f}% (< 95%)")
        
        if stats['legitimate']:
            fp_rate = (stats['legitimate']['false_positives'] / stats['legitimate']['total'] * 100)
            if fp_rate == 0:
                logger.info("No hay falsos positivos en requests legítimas")
            else:
                logger.info(f"Falsos positivos: {fp_rate:.1f}%")
        
        # Guardar resultados en JSON
        self._save_results_json()
    
    def _save_results_json(self):
        """Guarda los resultados completos en un archivo JSON"""
        filename = f"experiment_1_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            logger.info(f"\nResultados guardados en: {filename}")
        except Exception as e:
            logger.error(f"Error al guardar resultados JSON: {str(e)}")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Experimento 1: Detección de Ataques MITM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  python experiment_1_mitm_detection.py --total-requests 100 --mitm-percentage 30
  python experiment_1_mitm_detection.py --total-requests 300 --mitm-percentage 50
  python experiment_1_mitm_detection.py --total-requests 200 --mitm-percentage 20 --api-gateway http://localhost:5000 --num-tokens 8
        '''
    )
    
    parser.add_argument(
        '--total-requests',
        type=int,
        default=100,
        help='Número total de requests a realizar (default: 100)'
    )
    
    parser.add_argument(
        '--mitm-percentage',
        type=float,
        default=30,
        help='Porcentaje de requests que simularán ataques MITM, 0-100 (default: 30)'
    )
    
    parser.add_argument(
        '--api-gateway',
        type=str,
        default='http://localhost:5000',
        help='URL del API Gateway (default: http://localhost:5000)'
    )
    
    parser.add_argument(
        '--num-tokens',
        type=int,
        default=5,
        help='Número de tokens independientes a obtener (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.total_requests < 1:
        logger.error("--total-requests debe ser >= 1")
        return 1
    
    if not 0 <= args.mitm_percentage <= 100:
        logger.error("--mitm-percentage debe estar entre 0 y 100")
        return 1
    
    if args.num_tokens < 1:
        logger.error("--num-tokens debe ser >= 1")
        return 1
    
    try:
        experiment = MITMExperiment(
            api_gateway_url=args.api_gateway,
            total_requests=args.total_requests,
            mitm_percentage=args.mitm_percentage,
            num_tokens=args.num_tokens
        )
        
        success = experiment.run()
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
        return 1


if __name__ == '__main__':
    exit(main())
