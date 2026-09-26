import type {
    FeatureCollection,
    LineString,
    Point,
} from 'geojson';

import { routeColors } from '../../data/routeColors';
import { findRoute, tramRoutes, type Coordinate } from './routes';

export interface RouteStop {
    id: string;
    routeId: string;
    directionId: number;
    sequence: number;
    stopId: string;
    name: string;
    directionName: string;
    source: string;
    sourceDate: string;
    coordinates: Coordinate;
}

interface RawStopProperties {
    route: number;
    direction_id: number;
    stop_sequence: number;
    stop_id: string;
    stop_name: string;
    direction_name: string;
    source: string;
    source_date: string;
}

interface RouteFeatureProperties {
    id: string;
    name: string;
    color: string;
    load: number;
    directionId?: number;
}

interface StopFeatureProperties {
    id: string;
    routeId: string;
    name: string;
    color: string;
    directionId: number;
    sequence: number;
    directionName: string;
}

export type RawStopsGeoJson = FeatureCollection<Point, RawStopProperties>;
export type RoutesMapGeoJson = FeatureCollection<LineString, RouteFeatureProperties>;
export type StopsMapGeoJson = FeatureCollection<Point, StopFeatureProperties>;

export const fallbackRouteStops: RouteStop[] = tramRoutes.flatMap((route) => (
    route.stops.map((tramStop, index) => ({
        id: `${route.id}-0-${index + 1}-${tramStop.id}`,
        routeId: route.id,
        directionId: 0,
        sequence: index + 1,
        stopId: tramStop.id,
        name: tramStop.name,
        directionName: route.name,
        source: 'prototype',
        sourceDate: '',
        coordinates: tramStop.coordinates,
    }))
));

export const normaliseRouteStops = (collection: RawStopsGeoJson): RouteStop[] => (
    collection.features
        .map((feature) => {
            const properties = feature.properties;
            const routeId = String(properties.route);

            return {
                id: `${routeId}-${properties.direction_id}-${properties.stop_sequence}-${properties.stop_id}`,
                routeId,
                directionId: properties.direction_id,
                sequence: properties.stop_sequence,
                stopId: properties.stop_id,
                name: properties.stop_name,
                directionName: properties.direction_name,
                source: properties.source,
                sourceDate: properties.source_date,
                coordinates: feature.geometry.coordinates as Coordinate,
            };
        })
        .sort((first, second) => (
            Number(first.routeId) - Number(second.routeId)
            || first.directionId - second.directionId
            || first.sequence - second.sequence
        ))
);

export const routeStopsToGeoJson = (stops: RouteStop[]): StopsMapGeoJson => ({
    type: 'FeatureCollection',
    features: stops.map((tramStop) => ({
        type: 'Feature',
        properties: {
            id: tramStop.id,
            routeId: tramStop.routeId,
            name: tramStop.name,
            color: routeColors[tramStop.routeId],
            directionId: tramStop.directionId,
            sequence: tramStop.sequence,
            directionName: tramStop.directionName,
        },
        geometry: {
            type: 'Point',
            coordinates: tramStop.coordinates,
        },
    })),
});

export const routesFromStops = (stops: RouteStop[]): RoutesMapGeoJson => {
    const groupedStops = new Map<string, RouteStop[]>();

    stops.forEach((tramStop) => {
        const key = `${tramStop.routeId}:${tramStop.directionId}`;
        const current = groupedStops.get(key) ?? [];

        current.push(tramStop);
        groupedStops.set(key, current);
    });

    return {
        type: 'FeatureCollection',
        features: [...groupedStops.values()]
            .filter((directionStops) => directionStops.length > 1)
            .map((directionStops) => {
                const orderedStops = [...directionStops].sort((first, second) => first.sequence - second.sequence);
                const firstStop = orderedStops[0];
                const route = findRoute(firstStop.routeId);

                return {
                    type: 'Feature',
                    properties: {
                        id: firstStop.routeId,
                        name: firstStop.directionName,
                        color: routeColors[firstStop.routeId],
                        load: route.load,
                        directionId: firstStop.directionId,
                    },
                    geometry: {
                        type: 'LineString',
                        coordinates: orderedStops.map((tramStop) => tramStop.coordinates),
                    },
                };
            }),
    };
};

export const getUniqueStopOptions = (stops: RouteStop[]) => {
    const byRouteAndName = new Map<string, RouteStop>();

    stops.forEach((tramStop) => {
        const key = `${tramStop.routeId}:${tramStop.name.toLocaleLowerCase('ru')}`;

        if (!byRouteAndName.has(key)) {
            byRouteAndName.set(key, tramStop);
        }
    });

    return [...byRouteAndName.values()];
};

export const isRawStopsGeoJson = (value: unknown): value is RawStopsGeoJson => (
    typeof value === 'object'
    && value !== null
    && (value as { type?: string }).type === 'FeatureCollection'
    && Array.isArray((value as { features?: unknown[] }).features)
);
