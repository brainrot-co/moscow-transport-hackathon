import type { FeatureCollection, LineString, Point } from 'geojson';

import { routeColors } from '../../data/routeColors';

export type Coordinate = [longitude: number, latitude: number];

export interface TramStop {
    id: string;
    name: string;
    coordinates: Coordinate;
}

export interface TramRoute {
    id: string;
    name: string;
    load: number;
    coordinates: Coordinate[];
    stops: TramStop[];
}

interface RouteProperties {
    id: string;
    name: string;
    color: string;
    load: number;
}

interface StopProperties {
    id: string;
    routeId: string;
    name: string;
    color: string;
}

const stop = (
    routeId: string,
    index: number,
    name: string,
    coordinates: Coordinate,
): TramStop => ({
    id: `${routeId}-${index}`,
    name,
    coordinates,
});

// Prototype geometry follows the routes from the supplied reference. It is kept
// separately from the renderer so an API response can replace it later.
export const tramRoutes: TramRoute[] = [
    {
        id: '1',
        name: 'Чертаново Южное — Москворецкий рынок',
        load: 71,
        coordinates: [
            [37.603, 55.59], [37.601, 55.602], [37.6, 55.614],
            [37.606, 55.625], [37.614, 55.636], [37.625, 55.642],
            [37.635, 55.644],
        ],
        stops: [
            stop('1', 0, 'Чертаново Южное', [37.603, 55.59]),
            stop('1', 1, 'Улица Академика Янгеля', [37.6, 55.614]),
            stop('1', 2, 'Москворецкий рынок', [37.635, 55.644]),
        ],
    },
    {
        id: '5',
        name: 'Метро «Рижская» — Белорусский вокзал',
        load: 48,
        coordinates: [
            [37.635, 55.792], [37.625, 55.795], [37.614, 55.797],
            [37.604, 55.795], [37.596, 55.789], [37.586, 55.776],
        ],
        stops: [
            stop('5', 0, 'Метро «Рижская»', [37.635, 55.792]),
            stop('5', 1, 'МИИТ', [37.614, 55.797]),
            stop('5', 2, 'Белорусский вокзал', [37.586, 55.776]),
        ],
    },
    {
        id: '7',
        name: 'Метро «Бульвар Рокоссовского» — Белорусский вокзал',
        load: 58,
        coordinates: [
            [37.734, 55.815], [37.716, 55.811], [37.698, 55.805],
            [37.68, 55.799], [37.661, 55.793], [37.641, 55.786],
            [37.62, 55.78], [37.602, 55.778], [37.586, 55.776],
        ],
        stops: [
            stop('7', 0, 'Бульвар Рокоссовского', [37.734, 55.815]),
            stop('7', 1, 'Краснобогатырская улица', [37.698, 55.805]),
            stop('7', 2, 'Каланчёвская улица', [37.641, 55.786]),
            stop('7', 3, 'Белорусский вокзал', [37.586, 55.776]),
        ],
    },
    {
        id: '11',
        name: 'Усадьба Останкино — Восточное Измайлово',
        load: 64,
        coordinates: [
            [37.638, 55.824], [37.651, 55.818], [37.665, 55.813],
            [37.681, 55.807], [37.699, 55.803], [37.718, 55.802],
            [37.739, 55.803], [37.761, 55.8], [37.784, 55.795],
            [37.807, 55.79], [37.827, 55.787],
        ],
        stops: [
            stop('11', 0, 'Усадьба Останкино', [37.638, 55.824]),
            stop('11', 1, 'Преображенская площадь', [37.718, 55.802]),
            stop('11', 2, 'Измайловский проспект', [37.784, 55.795]),
            stop('11', 3, 'Восточное Измайлово', [37.827, 55.787]),
        ],
    },
    {
        id: '12',
        name: 'Восточное Измайлово — МЦК Дубровка',
        load: 73,
        coordinates: [
            [37.827, 55.787], [37.806, 55.782], [37.786, 55.776],
            [37.765, 55.768], [37.748, 55.759], [37.733, 55.749],
            [37.719, 55.739], [37.703, 55.73], [37.688, 55.722],
            [37.677, 55.718],
        ],
        stops: [
            stop('12', 0, 'Восточное Измайлово', [37.827, 55.787]),
            stop('12', 1, 'Шоссе Энтузиастов', [37.748, 55.759]),
            stop('12', 2, 'Авиамоторная улица', [37.719, 55.739]),
            stop('12', 3, 'МЦК Дубровка', [37.677, 55.718]),
        ],
    },
    {
        id: '17',
        name: 'Останкино — Медведково',
        load: 82,
        coordinates: [
            [37.638, 55.824], [37.635, 55.835], [37.638, 55.846],
            [37.645, 55.855], [37.649, 55.865], [37.654, 55.875],
            [37.663, 55.887],
        ],
        stops: [
            stop('17', 0, 'Останкино', [37.638, 55.824]),
            stop('17', 1, 'Улица Академика Королёва', [37.635, 55.835]),
            stop('17', 2, 'Сельскохозяйственная улица', [37.645, 55.855]),
            stop('17', 3, 'Медведково', [37.663, 55.887]),
        ],
    },
    {
        id: '25',
        name: 'Останкино — Метро «Сокольники»',
        load: 61,
        coordinates: [
            [37.638, 55.824], [37.646, 55.817], [37.654, 55.81],
            [37.662, 55.803], [37.671, 55.797], [37.68, 55.79],
        ],
        stops: [
            stop('25', 0, 'Останкино', [37.638, 55.824]),
            stop('25', 1, 'ВДНХ', [37.654, 55.81]),
            stop('25', 2, 'Ростокинский проезд', [37.671, 55.797]),
            stop('25', 3, 'Метро «Сокольники»', [37.68, 55.79]),
        ],
    },
    {
        id: '26',
        name: 'Метро «Университет» — Метро «Октябрьская»',
        load: 42,
        coordinates: [
            [37.535, 55.692], [37.546, 55.698], [37.558, 55.704],
            [37.571, 55.709], [37.584, 55.716], [37.597, 55.723],
            [37.609, 55.73],
        ],
        stops: [
            stop('26', 0, 'Метро «Университет»', [37.535, 55.692]),
            stop('26', 1, 'Ленинский проспект', [37.571, 55.709]),
            stop('26', 2, 'Метро «Октябрьская»', [37.609, 55.73]),
        ],
    },
    {
        id: '28',
        name: 'Метро «Сокол» — Проспект Маршала Жукова',
        load: 52,
        coordinates: [
            [37.515, 55.805], [37.506, 55.8], [37.497, 55.795],
            [37.487, 55.79], [37.479, 55.783], [37.47, 55.775],
        ],
        stops: [
            stop('28', 0, 'Метро «Сокол»', [37.515, 55.805]),
            stop('28', 1, 'Улица Алабяна', [37.497, 55.795]),
            stop('28', 2, 'Проспект Маршала Жукова', [37.47, 55.775]),
        ],
    },
    {
        id: '50',
        name: 'Дом культуры «Компрессор» — Метро «Новослободская»',
        load: 69,
        coordinates: [
            [37.699, 55.758], [37.687, 55.762], [37.674, 55.766],
            [37.659, 55.77], [37.644, 55.774], [37.628, 55.779],
            [37.613, 55.783], [37.601, 55.781],
        ],
        stops: [
            stop('50', 0, 'Дом культуры «Компрессор»', [37.699, 55.758]),
            stop('50', 1, 'Лефортовский мост', [37.674, 55.766]),
            stop('50', 2, 'Красные Ворота', [37.644, 55.774]),
            stop('50', 3, 'Метро «Новослободская»', [37.601, 55.781]),
        ],
    },
];

export const routesGeoJson: FeatureCollection<LineString, RouteProperties> = {
    type: 'FeatureCollection',
    features: tramRoutes.map((route) => ({
        type: 'Feature',
        properties: {
            id: route.id,
            name: route.name,
            color: routeColors[route.id],
            load: route.load,
        },
        geometry: {
            type: 'LineString',
            coordinates: route.coordinates,
        },
    })),
};

export const stopsGeoJson: FeatureCollection<Point, StopProperties> = {
    type: 'FeatureCollection',
    features: tramRoutes.flatMap((route) => route.stops.map((tramStop) => ({
        type: 'Feature' as const,
        properties: {
            id: tramStop.id,
            routeId: route.id,
            name: tramStop.name,
            color: routeColors[route.id],
        },
        geometry: {
            type: 'Point' as const,
            coordinates: tramStop.coordinates,
        },
    }))),
};

export const findRoute = (routeId: string) => (
    tramRoutes.find((route) => route.id === routeId) ?? tramRoutes[0]
);

