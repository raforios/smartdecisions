'''
    Prepares the routes of a demo day for the two demo companies.

    A demo of Rutas needs something to show: plans for the day, a plan in a bad
    order to optimise, routes run on previous days to compare against their
    plans, and the stock the sellers sell from. The companies are ours and
    invented, so all of it is generated here — and it goes through
    OPTIMIZATION's own functions, so it passes the same geofences and the same
    stock draw-down as a seller on the street.

    Every plan starts and ends at the company's depot, so a seller testing
    from the office can open and close the route. The depot is BearSoft's
    office for both companies until each company configures its own.

    Run it the morning of the demo, with that date:

        python -m tools.seed_demo_routes                 # simulation, today
        python -m tools.seed_demo_routes --date 2026-10-07 --yes

    Re-running a date skips the plans that already exist.

    It also writes `tools/samples/stock_<company>.xlsx`, the stock template
    filled with each company's SKUs, to try the stock upload in Rutas.
'''
import argparse
import io
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import boto3
import numpy as np
import pandas as pd
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OPTIMIZATION_PATH = ROOT / 'services' / 'optimization'
sys.path.insert(0, str(OPTIMIZATION_PATH))
# The service validates its environment on import, so it is loaded first.
load_dotenv(OPTIMIZATION_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.daily_stock import (  # noqa: E402
    DailyStockLoadSchema,
    SaleItemSchema,
    StockItemLoadSchema
)
from schemas.localization import (  # noqa: E402
    ExecutedPointCreateSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteUpdateSchema,
    PlannedPointSchema,
    PlannedRouteCreateSchema,
    PlannedRouteStatusEnum,
    VisitOutcome
)
from services.daily_stock import load_daily_stock  # noqa: E402
from services.exceptions import InvalidInputError  # noqa: E402
from services.localization import (  # noqa: E402
    create_planned_route,
    list_planned_routes,
    update_planned_route_status
)
from services.localization_executed import (  # noqa: E402
    close_executed_route,
    create_executed_route,
    register_executed_point
)
from services.optimization import order_stops  # noqa: E402

PROFILE = 'deploy_ml'
REGION = 'us-east-1'
BUCKET = 'ml-data-file-handler'
ZONE = ZoneInfo('America/La_Paz')
SAMPLES = ROOT / 'tools' / 'samples'

DEPOT_NAME = 'BearSoft'
DEPOT = (-16.543376949529225, -68.0718549258045)

SELLERS_PER_COMPANY = 4
STOPS_PER_PLAN = 10
PAST_DAYS = 3
GEOFENCE_METRES = 300.0
SEED = 20261005

# Stock template headers, in the order of `plantilla_stock.xlsx`.
STOCK_HEADERS = {'snapshot_date': 'Fecha', 'product_id': 'Producto ID',
                 'product_name': 'Producto', 'on_hand': 'Existencia',
                 'committed': 'Comprometido'}


@dataclass(frozen = True)
class Company:
    '''
        A demo company and the user its first seller logs in with.
    '''
    owner: str
    slug: str
    seller_user: str


COMPANIES = (
    Company('Distribuidora Andina S.R.L.', 'andina', 'vendedor.demo@bearsoft.com.bo'),
    Company('Comercial Illimani S.R.L.', 'illimani', 'vendedor@raforios.com'),
)


def _session():
    '''
        The deployment profile.

        Returns:
            boto3.Session: Session with our credentials.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = REGION)


def _query(
    resource,
    table: str,
    owner: str
) -> List[Dict[str, Any]]:
    '''
        Every item of one owner in an INGEST table.

        Args:
            resource: DynamoDB resource.
            table (str): Table name.
            owner (str): Owner key.

        Returns:
            List[Dict[str, Any]]: The items.
    '''
    items: List[Dict[str, Any]] = []
    arguments: Dict[str, Any] = {'KeyConditionExpression': Key('owner_email').eq(owner)}
    while True:
        page = resource.Table(table).query(**arguments)
        items.extend(page['Items'])
        if 'LastEvaluatedKey' not in page:
            return items
        arguments['ExclusiveStartKey'] = page['LastEvaluatedKey']


def _stock_frame(
    resource,
    owner: str
) -> pd.DataFrame:
    '''
        The company's stock photo as INGEST stored it.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.

        Returns:
            pd.DataFrame: product_id, product_name, on_hand, committed.
    '''
    datasets = [item for item in resource.Table('ingest_datasets').scan()['Items']
                if item.get('owner_email') == owner and item.get('stock_s3_key')]
    key = max(datasets, key = lambda item: item['created_at'])['stock_s3_key']
    body = _session().client('s3').get_object(Bucket = BUCKET, Key = key)['Body'].read()
    frame = pd.read_csv(io.BytesIO(body))
    frame['available'] = (frame['on_hand'] - frame.get('committed', 0).fillna(0)).clip(lower = 0)
    return frame[frame['available'] > 0]


def _portfolios(clients: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    '''
        The clients with coordinates of the busiest sellers.

        Args:
            clients (List[Dict[str, Any]]): The client master of the company.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Seller name to their clients.
    '''
    by_seller: Dict[str, List[Dict[str, Any]]] = {}
    for client in clients:
        if client.get('seller') and client.get('latitude') and client.get('longitude'):
            by_seller.setdefault(client['seller'], []).append(client)
    ranked = sorted(by_seller, key = lambda seller: len(by_seller[seller]), reverse = True)
    return {seller: by_seller[seller] for seller in ranked[:SELLERS_PER_COMPANY]}


def _ordered(
    clients: List[Dict[str, Any]],
    shuffle: Optional[random.Random] = None
) -> List[Dict[str, Any]]:
    '''
        Clients in visiting order from the depot: OPTIMIZATION's own order, or
        shuffled when the plan is meant to be optimised.

        Args:
            clients (List[Dict[str, Any]]): Clients to visit.
            shuffle (random.Random | None): Generator for a deliberately bad order.

        Returns:
            List[Dict[str, Any]]: Clients in order.
    '''
    if shuffle is not None:
        bad = list(clients)
        shuffle.shuffle(bad)
        return bad
    points = np.array([DEPOT] + [(float(c['latitude']), float(c['longitude']))
                                 for c in clients])
    order = order_stops(points)
    return [clients[index - 1] for index in order if index != 0]


def _plan_points(clients: List[Dict[str, Any]]) -> List[PlannedPointSchema]:
    '''
        Depot, the clients, depot.

        Args:
            clients (List[Dict[str, Any]]): Clients in visiting order.

        Returns:
            List[PlannedPointSchema]: The stops.
    '''
    depot = {'point_name': DEPOT_NAME, 'latitude': DEPOT[0], 'longitude': DEPOT[1]}
    stops = [depot] + [{'point_name': c['name'][:100], 'client_id': c['id'],
                        'latitude': float(c['latitude']), 'longitude': float(c['longitude'])}
                       for c in clients] + [depot]
    return [PlannedPointSchema(secuencial = position, **stop)
            for position, stop in enumerate(stops, start = 1)]


def _create_plan(
    resource,
    owner: str,
    header: Dict[str, Any],
    clients: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    '''
        Creates and activates a plan, or skips it when its code exists.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.
            header (Dict[str, Any]): route_code, route_name, seller, plan_date.
            clients (List[Dict[str, Any]]): Clients in visiting order.

        Returns:
            Dict[str, Any] | None: The plan, or None when it already existed.
    '''
    existing = {plan['route_code'] for plan in list_planned_routes(resource, owner)}
    if header['route_code'] in existing:
        return None
    plan = create_planned_route(resource, owner, PlannedRouteCreateSchema(
        **header, points = _plan_points(clients)
    ))
    return update_planned_route_status(resource, owner, plan['id'],
                                       PlannedRouteStatusEnum.ACTIVE)


def _run_plan(
    resource,
    owner: str,
    plan: Dict[str, Any],
    run: Tuple[str, pd.DataFrame, random.Random]
) -> int:
    '''
        Runs a past plan as a seller would: starts at the depot, visits most
        stops —selling at some, finding others closed—, skips a few, and closes
        back at the depot.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.
            plan (Dict[str, Any]): The plan, of a past day.
            run (Tuple[str, pd.DataFrame, random.Random]): Who runs it, the
                stock to sell from and the generator.

        Returns:
            int: Visits registered.
    '''
    seller, stock, rng = run
    day = date.fromisoformat(plan['plan_date'])
    clock = datetime.combine(day, datetime.min.time(), ZONE).replace(hour = 8)
    route = create_executed_route(resource, owner, ExecutedRouteCreateSchema(
        seller = seller, start_time = clock.isoformat(), planned_route_id = plan['id'],
        start_latitude = DEPOT[0], start_longitude = DEPOT[1],
        max_distance_start_point = GEOFENCE_METRES
    ))
    visits = 0
    for stop in plan['points'][1:-1]:
        clock += timedelta(minutes = rng.randint(15, 30))
        if rng.random() < 0.2:
            continue                                     # a stop not reached
        outcome = rng.choices([VisitOutcome.SALE, VisitOutcome.NO_SALE, VisitOutcome.CLOSED],
                              weights = [0.65, 0.25, 0.10])[0]
        items = []
        if outcome is VisitOutcome.SALE:
            # Only SKUs with room to spare: a demo sale should not be the one
            # that empties a shelf.
            plenty = stock[stock['available'] >= 50]
            picked = plenty.sample(min(rng.randint(1, 3), len(plenty)),
                                   random_state = rng.randint(0, 9999))
            items = [SaleItemSchema(sku = str(row['product_id']), quantity = rng.randint(1, 4))
                     for _, row in picked.iterrows()]
        point = {'executed_route_id': route['id'], 'timestamp': clock.isoformat(),
                 'latitude': float(stop['latitude']), 'longitude': float(stop['longitude']),
                 'client_id': stop.get('client_id')}
        try:
            register_executed_point(resource, owner, ExecutedPointCreateSchema(
                **point, outcome = outcome, items = items,
                order_id = f'{plan["route_code"]}-{visits + 1}' if items else None
            ))
        except InvalidInputError:
            # The shelf ran out, as it would on the street: the visit stays,
            # without the sale.
            register_executed_point(resource, owner, ExecutedPointCreateSchema(
                **point, outcome = VisitOutcome.NO_SALE
            ))
        visits += 1
    clock += timedelta(minutes = 40)
    close_executed_route(resource, owner, route['id'], ExecutedRouteUpdateSchema(
        end_time = clock.isoformat(), end_latitude = DEPOT[0], end_longitude = DEPOT[1],
        max_distance_end_point = GEOFENCE_METRES
    ))
    return visits


def _load_stock(
    resource,
    owner: str,
    day: date,
    stock: pd.DataFrame
) -> None:
    '''
        Opens a day with the company's stock.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.
            day (date): The day.
            stock (pd.DataFrame): The stock photo.
    '''
    load_daily_stock(resource, owner, DailyStockLoadSchema(date = day.isoformat(), items = [
        StockItemLoadSchema(sku = str(row['product_id']),
                            product_name = str(row.get('product_name') or '')[:150] or None,
                            quantity = float(row['available']))
        for _, row in stock.iterrows()
    ]))


def _write_stock_sample(
    company: Company,
    stock: pd.DataFrame,
    day: date
) -> Path:
    '''
        The stock template filled with the company's SKUs, to try the upload.

        Args:
            company (Company): The company.
            stock (pd.DataFrame): The stock photo.
            day (date): The date the sample carries.

        Returns:
            Path: Where it was written.
    '''
    frame = stock.assign(snapshot_date = day.isoformat())
    columns = [column for column in STOCK_HEADERS if column in frame.columns]
    sample = frame[columns].rename(columns = STOCK_HEADERS)
    destination = SAMPLES / f'stock_{company.slug}.xlsx'
    sample.to_excel(destination, index = False, sheet_name = 'Datos')
    return destination


def _link_seller(
    resource,
    company: Company,
    seller: str
) -> None:
    '''
        Makes the company's seller user the one behind its busiest seller, so
        the phone shows that seller's plans. A link that exists is left alone.

        Args:
            resource: DynamoDB resource.
            company (Company): The company.
            seller (str): Seller name as the file writes it.
    '''
    linked = [item for item in _query(resource, 'ingest_sellers', company.owner)
              if item.get('user_email') == company.seller_user]
    if linked:
        return
    resource.Table('ingest_sellers').update_item(
        Key = {'owner_email': company.owner, 'id': seller},
        UpdateExpression = 'SET user_email = :u',
        ExpressionAttributeValues = {':u': company.seller_user}
    )


def seed_company(
    resource,
    company: Company,
    demo_day: date,
    write: bool
) -> None:
    '''
        Plans, past runs, stock and the stock sample of one company.

        Args:
            resource: DynamoDB resource.
            company (Company): The company.
            demo_day (date): The day of the demo.
            write (bool): False to report without writing.
    '''
    rng = random.Random(f'{SEED}{company.slug}{demo_day}')
    stock = _stock_frame(resource, company.owner)
    portfolios = _portfolios(_query(resource, 'ingest_clients', company.owner))
    linked = {item['id']: item.get('user_email')
              for item in _query(resource, 'ingest_sellers', company.owner)}
    print(f'\n{company.owner}: {len(stock)} SKU con stock, vendedores {list(portfolios)}')
    if not write:
        return

    sample = _write_stock_sample(company, stock, demo_day)
    print(f'  archivo de stock -> {sample}')
    _link_seller(resource, company, next(iter(portfolios)))
    linked[next(iter(portfolios))] = linked.get(next(iter(portfolios))) or company.seller_user

    for offset in range(PAST_DAYS, -1, -1):
        day = demo_day - timedelta(days = offset)
        _load_stock(resource, company.owner, day, stock)
        for seller, clients in portfolios.items():
            chosen = rng.sample(clients, min(STOPS_PER_PLAN, len(clients)))
            plan = _create_plan(resource, company.owner, {
                'route_code': f'DEMO-{seller[:20].upper().replace(" ", "_")}-{day}',
                'route_name': f'{seller} — {day.strftime("%d/%m")}',
                'seller': seller, 'plan_date': day
            }, _ordered(chosen))
            if plan and offset > 0:
                visits = _run_plan(resource, company.owner, plan,
                                   (linked.get(seller) or seller, stock, rng))
                print(f'  {day} {seller}: plan y recorrido ({visits} visitas)')
            elif plan:
                print(f'  {day} {seller}: plan del día')

    pool = [client for clients in portfolios.values() for client in clients]
    bad = _create_plan(resource, company.owner, {
        'route_code': f'DEMO-OPTIMIZAR-{demo_day}',
        'route_name': f'Ruta para optimizar — {demo_day.strftime("%d/%m")}',
        'plan_date': demo_day
    }, _ordered(rng.sample(pool, min(12, len(pool))), shuffle = rng))
    if bad:
        print(f'  {demo_day}: plan en mal orden para Optimizar')


def reset_demo(
    resource,
    owner: str,
    days: set
) -> Tuple[int, int]:
    '''
        Deletes the DEMO-* plans of the given days and the runs made against
        them. Nothing else of the company is touched.

        Args:
            resource: DynamoDB resource.
            owner (str): Owner key.
            days (set): ISO days to clear.

        Returns:
            Tuple[int, int]: Plans and runs deleted.
    '''
    plans = [plan for plan in _query(resource, 'optimization_planned_routes', owner)
             if str(plan.get('route_code', '')).startswith('DEMO-')
             and plan.get('plan_date') in days]
    ids = {plan['id'] for plan in plans}
    runs = [run for run in _query(resource, 'optimization_executed_routes', owner)
            if run.get('planned_route_id') in ids]
    for table, items in (('optimization_planned_routes', plans),
                         ('optimization_executed_routes', runs)):
        with resource.Table(table).batch_writer() as batch:
            for item in items:
                batch.delete_item(Key = {'owner_email': owner, 'id': item['id']})
    return len(plans), len(runs)


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--date', default = None, help = 'Demo day, YYYY-MM-DD. Today by default.')
    parser.add_argument('--yes', action = 'store_true', help = 'Write for real.')
    parser.add_argument('--reset', action = 'store_true',
                        help = 'Delete the DEMO-* plans and runs of those days first.')
    arguments = parser.parse_args(argument_list)

    demo_day = (date.fromisoformat(arguments.date) if arguments.date
                else datetime.now(ZONE).date())
    resource = _session().resource('dynamodb')
    if arguments.reset and arguments.yes:
        days = {(demo_day - timedelta(days = offset)).isoformat()
                for offset in range(PAST_DAYS + 1)}
        for company in COMPANIES:
            removed = reset_demo(resource, company.owner, days)
            print(f'{company.owner}: borrados {removed[0]} plan(es) '
                  f'y {removed[1]} recorrido(s) DEMO')
    for company in COMPANIES:
        seed_company(resource, company, demo_day, arguments.yes)
    if not arguments.yes:
        print('\nSimulación: no se escribió nada. Repite con --yes.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
