'''
    The bench of projection models.

    One place, one signature: every model takes the observed series and how many
    steps to project, and returns that many values. Nothing else. That is what
    lets the service run all of them over the same data and compare them without
    knowing what any of them does.

    Which models are here is a judgement about the data, not about ambition. The
    exchange-rate series is short — it starts at the float regime — and short
    series punish complex models: they have too many parameters to estimate from
    too few points, and end up fitting noise. So the bench holds classical
    methods that estimate two or three parameters at most, plus the naive
    forecast, which in exchange rates is the benchmark nobody beats easily.

    Deliberately absent: ARIMA and its seasonal variants. With seventy
    observations there is not enough to identify their orders, and a model
    presented as sophisticated while performing worse than "tomorrow is the same
    as today" is a liability in front of a client. When the series is long
    enough to estimate them, they belong here.
'''
from typing import Callable, Dict, List

import numpy as np

from services.environment import load_and_validate_env_vars


ENV_VARS = load_and_validate_env_vars({
    'RATE_HOLT_ALPHA': float,
    'RATE_HOLT_BETA': float,
    'RATE_HOLT_PHI': float,
    'RATE_SES_ALPHA': float,
    'RATE_MOVING_AVERAGE_WINDOW': int,
    'RATE_THETA_ALPHA': float,
})

# Suavizado de Holt: nivel, tendencia y amortiguación. Ajustados minimizando el
# error del backtest sobre la serie guardada.
ALPHA = ENV_VARS['RATE_HOLT_ALPHA']
BETA = ENV_VARS['RATE_HOLT_BETA']
PHI = ENV_VARS['RATE_HOLT_PHI']

# Suavizado exponencial simple: sin tendencia, sólo nivel.
SES_ALPHA = ENV_VARS['RATE_SES_ALPHA']

# Ventana del promedio móvil.
MOVING_WINDOW = ENV_VARS['RATE_MOVING_AVERAGE_WINDOW']

# Suavizado de la línea theta.
THETA_ALPHA = ENV_VARS['RATE_THETA_ALPHA']


def naive(values: List[float], days_ahead: int) -> List[float]:
    '''
        Repite la última observación.

        Es el rival a vencer, no un relleno: en tipos de cambio, a horizontes
        cortos, casi ningún modelo le gana de forma sostenida. Cualquier
        proyección que no lo supere no se está ganando su lugar.

        Args:
            values (List[float]): Serie observada, la más antigua primero.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    return [float(values[-1])] * days_ahead


def mean(values: List[float], days_ahead: int) -> List[float]:
    '''
        Repite el promedio de toda la serie.

        Sirve de contraste: si le gana a los demás, la serie no tiene tendencia
        y cualquier proyección con pendiente está leyendo ruido.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    return [float(np.mean(values))] * days_ahead


def drift(values: List[float], days_ahead: int) -> List[float]:
    '''
        Camino aleatorio con deriva: extiende la pendiente entre el primer y el
        último punto.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)
    slope = (values[-1] - values[0]) / (len(values) - 1)
    return [float(values[-1] + slope * step) for step in range(1, days_ahead + 1)]


def linear(values: List[float], days_ahead: int) -> List[float]:
    '''
        Recta de mínimos cuadrados sobre toda la serie.

        Está aquí para poder mostrarla perdiendo: fue el modelo por defecto
        hasta que el backtest mostró que erraba el doble que la tendencia
        amortiguada, porque extrapola para siempre una pendiente que el mercado
        no respeta.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)
    positions = np.arange(len(values), dtype = float)
    slope, intercept = np.polyfit(positions, np.array(values, dtype = float), 1)
    future = np.arange(len(values), len(values) + days_ahead, dtype = float)
    return [float(value) for value in slope * future + intercept]


def moving_average(values: List[float], days_ahead: int) -> List[float]:
    '''
        Repite el promedio de los últimos días.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    window = values[-MOVING_WINDOW:] if len(values) >= MOVING_WINDOW else values
    return [float(np.mean(window))] * days_ahead


def simple_exponential(values: List[float], days_ahead: int) -> List[float]:
    '''
        Suavizado exponencial simple: nivel que sigue a la serie, sin tendencia.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    level = values[0]
    for value in values[1:]:
        level = SES_ALPHA * value + (1 - SES_ALPHA) * level
    return [float(level)] * days_ahead


def holt(values: List[float], days_ahead: int) -> List[float]:
    '''
        Suavizado de Holt con tendencia lineal, sin amortiguar.

        El contraste directo de la tendencia amortiguada: misma mecánica, pero
        la tendencia no se apaga. En una serie que se aplana, esta se pasa de
        largo y la otra no; verlas juntas muestra cuánto pesa la amortiguación.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    return _holt(values, days_ahead, phi = 1.0)


def damped_trend(values: List[float], days_ahead: int) -> List[float]:
    '''
        Suavizado de Holt con la tendencia amortiguada.

        El nivel sigue a las últimas observaciones y la tendencia **se
        desvanece**: cada día más lejano hereda menos de la deriva reciente. Eso
        es lo que impide que la proyección se dispare, y por lo que este es el
        modelo por defecto.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    return _holt(values, days_ahead, phi = PHI)


def _holt(values: List[float], days_ahead: int, phi: float) -> List[float]:
    '''
        Mecánica común de Holt, con y sin amortiguación.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.
            phi (float): Factor de amortiguación; 1.0 la desactiva.

        Returns:
            List[float]: Valores proyectados.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)

    level, trend = values[0], values[1] - values[0]
    for value in values[1:]:
        previous = level
        level = ALPHA * value + (1 - ALPHA) * (level + phi * trend)
        trend = BETA * (level - previous) + (1 - BETA) * phi * trend

    damping = np.cumsum(phi ** np.arange(1, days_ahead + 1))
    return [float(value) for value in level + damping * trend]


def theta(values: List[float], days_ahead: int) -> List[float]:
    '''
        Método Theta: promedia una recta de largo plazo con un suavizado que
        sigue los movimientos recientes.

        Ganó la competencia M3 y sigue siendo difícil de superar en series
        cortas, que es exactamente el caso aquí. La idea es simple: una mitad de
        la respuesta la pone la tendencia de fondo y la otra el nivel actual, así
        que ni ignora la dirección ni la extrapola sin freno.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    if len(values) < 3:
        return naive(values, days_ahead)

    # Línea theta-cero: la recta de regresión, extendida.
    straight = linear(values, days_ahead)

    # Línea theta-dos: suavizado exponencial sobre la serie, que carga el peso
    # en lo reciente.
    level = values[0]
    for value in values[1:]:
        level = THETA_ALPHA * value + (1 - THETA_ALPHA) * level
    smoothed = [float(level)] * days_ahead

    return [(one + two) / 2 for one, two in zip(straight, smoothed)]


# El registro es el contrato: agregar un modelo es agregar una entrada, y todo
# lo que compara, mide y publica lo recorre sin conocer ninguno en particular.
MODELS: Dict[str, Callable[[List[float], int], List[float]]] = {
    'NAIVE': naive,
    'MEAN': mean,
    'DRIFT': drift,
    'LINEAR': linear,
    'MOVING_AVERAGE': moving_average,
    'SIMPLE_EXPONENTIAL': simple_exponential,
    'HOLT': holt,
    'DAMPED_TREND': damped_trend,
    'THETA': theta,
}
