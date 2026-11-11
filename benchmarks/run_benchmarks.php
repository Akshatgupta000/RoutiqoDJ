<?php
/**
 * Routiqo Production Performance Benchmark
 * 
 * Accurately measures:
 * 1. Voronoi Spatial Allocation: Mileage reduction and allocation latency
 * 2. Nearest-Neighbor Routing: Distance reduction (Random order vs NN + 2-Opt)
 * 3. OSRM Road Distance vs Haversine Straight-line Distance
 * 4. Dispatch Compute Latency across 5 test sets (30, 35, 40, 45, 50 points)
 * 
 * Strict compliance:
 * - Fixed random seed for 100% reproducibility
 * - Minimum 5 runs per test set (reporting min, avg, max)
 * - Raw run outputs + structured summary tables
 */

require_once __DIR__ . '/../Backend/vendor/autoload.php';

use App\Helpers\DistanceHelper;
use App\Helpers\RouteOptimizer;
use App\Models\Order;
use App\Enums\OrderPriority;
use Illuminate\Support\Collection;

// Boot Laravel framework
$app = require_once __DIR__ . '/../Backend/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

// Fixed seed for strict reproducibility
$masterSeed = 42;
mt_srand($masterSeed);

$hubs = [
    [
        'id' => 'hub_brooklyn',
        'name' => 'Brooklyn Distribution Hub',
        'latitude' => 40.6782,
        'longitude' => -73.9442,
        'riders' => [
            ['id' => 'van_bk_01', 'name' => 'Van BK-01', 'capacity' => 10],
            ['id' => 'van_bk_02', 'name' => 'Van BK-02', 'capacity' => 9],
            ['id' => 'van_bk_03', 'name' => 'Van BK-03', 'capacity' => 8],
        ]
    ],
    [
        'id' => 'hub_queens',
        'name' => 'Queens Fulfillment Center',
        'latitude' => 40.7282,
        'longitude' => -73.7949,
        'riders' => [
            ['id' => 'truck_qn_01', 'name' => 'Truck QN-01', 'capacity' => 12],
            ['id' => 'truck_qn_02', 'name' => 'Truck QN-02', 'capacity' => 11],
        ]
    ]
];

$setSizes = [30, 35, 40, 45, 50];
$timingRunsPerSet = 5;

// Query OSRM driving distance with caching
function getOsrmDrivingDistanceKm(array $coords): ?float {
    if (count($coords) < 2) return 0.0;
    
    $pts = implode(';', array_map(fn($c) => round($c[1], 6) . ',' . round($c[0], 6), $coords));
    $url = "https://router.project-osrm.org/route/v1/driving/{$pts}?overview=false";
    
    static $cache = [];
    if (isset($cache[$pts])) {
        return $cache[$pts];
    }
    
    $ctx = stream_context_create([
        'http' => [
            'timeout' => 8,
            'user_agent' => 'Routiqo-Benchmark/1.0'
        ]
    ]);
    
    usleep(100000); // 100ms throttle for public OSRM server
    
    $raw = @file_get_contents($url, false, $ctx);
    if ($raw !== false) {
        $json = json_decode($raw, true);
        if (($json['code'] ?? '') === 'Ok' && isset($json['routes'][0]['distance'])) {
            $distKm = $json['routes'][0]['distance'] / 1000.0;
            $cache[$pts] = $distKm;
            return $distKm;
        }
    }
    
    return null; // fallback to straight-line estimate
}

// Generate deterministic delivery points
function generatePoints(int $count, array $hubs, int $setSeed): array {
    mt_srand($setSeed);
    $points = [];
    for ($i = 0; $i < $count; $i++) {
        $targetHub = ($i % 2 === 0) ? $hubs[0] : $hubs[1];
        $latOffset = (mt_rand(-350, 350) / 10000.0); // ~3.8km
        $lonOffset = (mt_rand(-500, 500) / 10000.0); // ~4.2km
        
        $order = new Order();
        $order->id = "ord_" . ($i + 1);
        $order->latitude = round($targetHub['latitude'] + $latOffset, 6);
        $order->longitude = round($targetHub['longitude'] + $lonOffset, 6);
        $order->priority = OrderPriority::Normal;
        
        $points[] = $order;
    }
    return $points;
}

// Assign to nearest hub (Voronoi Partitioning)
function assignVoronoiHub(Order $order, array $hubs): array {
    $bestHub = null;
    $minDist = INF;
    foreach ($hubs as $hub) {
        $dist = DistanceHelper::kmBetween(
            (float)$order->latitude, (float)$order->longitude,
            $hub['latitude'], $hub['longitude']
        );
        if ($dist < $minDist) {
            $minDist = $dist;
            $bestHub = $hub;
        }
    }
    return $bestHub;
}

// Cluster orders into vehicle capacity buckets
function clusterOrdersIntoRiders(Collection $orders, array $riders, float $depotLat, float $depotLon): array {
    $sorted = $orders->sort(function (Order $a, Order $b) use ($depotLat, $depotLon) {
        $angleA = atan2($a->latitude - $depotLat, $a->longitude - $depotLon);
        $angleB = atan2($b->latitude - $depotLat, $b->longitude - $depotLon);
        return ($angleA === $angleB) ? ($a->id <=> $b->id) : ($angleA <=> $angleB);
    })->values();

    $buckets = [];
    $cursor = 0;
    $totalOrders = $sorted->count();
    $riderCol = collect($riders)->sortBy('id')->values();

    foreach ($riderCol as $index => $rider) {
        $remaining = $totalOrders - $cursor;
        if ($remaining <= 0) {
            $buckets[$rider['id']] = collect();
            continue;
        }
        $remVehicles = $riderCol->count() - $index;
        $fairShare = (int) ceil($remaining / $remVehicles);
        $take = min($fairShare, $rider['capacity'], $remaining);
        $slice = $sorted->slice($cursor, $take)->values();
        $cursor += $slice->count();
        $buckets[$rider['id']] = $slice;
    }

    return $buckets;
}

echo "========================================================================================\n";
echo "ROUTIQO PERFORMANCE BENCHMARK SUITE\n";
echo "Environment: PHP " . PHP_VERSION . " | Laravel 11 | OSRM Engine\n";
echo "Fixed Seed: {$masterSeed} | 5 Test Sets: " . implode(', ', $setSizes) . " delivery points\n";
echo "Active Hubs: Brooklyn Hub (3 riders) & Queens Hub (2 riders) | Total Fleet: 5 Riders (Cap: 50)\n";
echo "========================================================================================\n\n";

$results = [];

foreach ($setSizes as $setIndex => $count) {
    $setNum = $setIndex + 1;
    $setSeed = $masterSeed + ($setIndex * 100);
    $orders = generatePoints($count, $hubs, $setSeed);
    
    echo "----------------------------------------------------------------------------------------\n";
    echo "TEST SET {$setNum}: {$count} DELIVERY POINTS (Seed: {$setSeed})\n";
    echo "----------------------------------------------------------------------------------------\n";
    
    // 1. Measure Latency over 5 runs
    $timingRuns = [];
    for ($r = 1; $r <= $timingRunsPerSet; $r++) {
        $t0 = hrtime(true);
        
        // Voronoi allocation
        $hubBuckets = [];
        foreach ($orders as $order) {
            $h = assignVoronoiHub($order, $hubs);
            $hubBuckets[$h['id']][] = $order;
        }
        $t1 = hrtime(true);
        
        // Route clustering & Nearest-Neighbor + 2-opt optimization
        $routes = [];
        foreach ($hubs as $hub) {
            $hubOrders = collect($hubBuckets[$hub['id']] ?? []);
            if ($hubOrders->isEmpty()) continue;
            
            $riderBuckets = clusterOrdersIntoRiders($hubOrders, $hub['riders'], $hub['latitude'], $hub['longitude']);
            $opt = new RouteOptimizer($hub['latitude'], $hub['longitude']);
            
            foreach ($riderBuckets as $riderId => $bucket) {
                if ($bucket->isEmpty()) continue;
                $tour = $opt->buildShortestDistanceTour($bucket);
                $routes[$riderId] = $tour;
            }
        }
        $t2 = hrtime(true);
        
        $allocMs = ($t1 - $t0) / 1e6;
        $routeMs = ($t2 - $t1) / 1e6;
        $totalMs = ($t2 - $t0) / 1e6;
        
        $timingRuns[] = [
            'run' => $r,
            'alloc_ms' => $allocMs,
            'route_ms' => $routeMs,
            'total_ms' => $totalMs
        ];
    }
    
    $allocTimes = array_column($timingRuns, 'alloc_ms');
    $routeTimes = array_column($timingRuns, 'route_ms');
    $totalTimes = array_column($timingRuns, 'total_ms');
    
    $avgAlloc = array_sum($allocTimes) / count($allocTimes);
    $avgRoute = array_sum($routeTimes) / count($routeTimes);
    $avgTotal = array_sum($totalTimes) / count($totalTimes);
    $minTotal = min($totalTimes);
    $maxTotal = max($totalTimes);
    
    // 2. Measure Route Distances: Random Order vs Optimized Nearest-Neighbor (+ 2-opt)
    $hubBuckets = [];
    foreach ($orders as $order) {
        $h = assignVoronoiHub($order, $hubs);
        $hubBuckets[$h['id']][] = $order;
    }
    
    $activeRiders = 0;
    $setBeforeHaversine = 0.0;
    $setAfterHaversine = 0.0;
    $setBeforeOsrm = 0.0;
    $setAfterOsrm = 0.0;
    $osrmStatus = 'OK';
    
    $riderBreakdown = [];
    
    foreach ($hubs as $hub) {
        $hubOrders = collect($hubBuckets[$hub['id']] ?? []);
        if ($hubOrders->isEmpty()) continue;
        
        $riderBuckets = clusterOrdersIntoRiders($hubOrders, $hub['riders'], $hub['latitude'], $hub['longitude']);
        $opt = new RouteOptimizer($hub['latitude'], $hub['longitude']);
        
        foreach ($riderBuckets as $riderId => $bucket) {
            if ($bucket->isEmpty()) continue;
            $activeRiders++;
            $stops = $bucket->values()->all();
            
            // (a) RANDOM ORDER (Arrival sequence shuffled with deterministic seed)
            $randomStops = $stops;
            // Deterministic shuffle for this rider route
            mt_srand($setSeed + crc32($riderId));
            shuffle($randomStops);
            
            $distBeforeH = $opt->tourDistanceKm($randomStops);
            
            // OSRM coordinates for random tour
            $ptsRandom = [ [$hub['latitude'], $hub['longitude']] ];
            foreach ($randomStops as $s) {
                $ptsRandom[] = [(float)$s->latitude, (float)$s->longitude];
            }
            $ptsRandom[] = [$hub['latitude'], $hub['longitude']];
            
            $distBeforeO = getOsrmDrivingDistanceKm($ptsRandom);
            if ($distBeforeO === null) {
                $osrmStatus = 'FALLBACK_STRAIGHT_LINE';
                $distBeforeO = $distBeforeH;
            }
            
            // (b) OPTIMIZED ORDER: Nearest-Neighbor + 2-Opt
            $optTour = $opt->buildShortestDistanceTour($bucket);
            $distAfterH = $opt->tourDistanceKm($optTour);
            
            $ptsOpt = [ [$hub['latitude'], $hub['longitude']] ];
            foreach ($optTour as $s) {
                $ptsOpt[] = [(float)$s->latitude, (float)$s->longitude];
            }
            $ptsOpt[] = [$hub['latitude'], $hub['longitude']];
            
            $distAfterO = getOsrmDrivingDistanceKm($ptsOpt);
            if ($distAfterO === null) {
                $osrmStatus = 'FALLBACK_STRAIGHT_LINE';
                $distAfterO = $distAfterH;
            }
            
            $setBeforeHaversine += $distBeforeH;
            $setAfterHaversine += $distAfterH;
            $setBeforeOsrm += $distBeforeO;
            $setAfterOsrm += $distAfterO;
            
            $riderBreakdown[] = [
                'hub' => $hub['name'],
                'rider_id' => $riderId,
                'stops_count' => count($stops),
                'random_haversine_km' => round($distBeforeH, 2),
                'opt_haversine_km' => round($distAfterH, 2),
                'reduction_haversine_pct' => round((($distBeforeH - $distAfterH) / $distBeforeH) * 100, 2),
                'random_osrm_km' => round($distBeforeO, 2),
                'opt_osrm_km' => round($distAfterO, 2),
                'reduction_osrm_pct' => round((($distBeforeO - $distAfterO) / $distBeforeO) * 100, 2),
            ];
        }
    }
    
    // 3. Voronoi Partitioning Mileage Impact:
    // Compare Non-Voronoi (random hub assignment across city) vs Voronoi Partitioning
    mt_srand($setSeed + 999);
    $shuffledAll = $orders;
    shuffle($shuffledAll);
    $splitPoint = count($hubBuckets['hub_brooklyn'] ?? []);
    $nonVoronoiBk = array_slice($shuffledAll, 0, $splitPoint);
    $nonVoronoiQn = array_slice($shuffledAll, $splitPoint);
    
    $optBk = new RouteOptimizer($hubs[0]['latitude'], $hubs[0]['longitude']);
    $optQn = new RouteOptimizer($hubs[1]['latitude'], $hubs[1]['longitude']);
    
    $nonVoronoiTotalKm = $optBk->tourDistanceKm($optBk->buildShortestDistanceTour(collect($nonVoronoiBk)))
                       + $optQn->tourDistanceKm($optQn->buildShortestDistanceTour(collect($nonVoronoiQn)));
    
    $voronoiTotalKm = $optBk->tourDistanceKm($optBk->buildShortestDistanceTour(collect($hubBuckets['hub_brooklyn'] ?? [])))
                    + $optQn->tourDistanceKm($optQn->buildShortestDistanceTour(collect($hubBuckets['hub_queens'] ?? [])));
    
    $voronoiSavingsPct = (($nonVoronoiTotalKm - $voronoiTotalKm) / $nonVoronoiTotalKm) * 100;
    
    $pctReductionHaversine = (($setBeforeHaversine - $setAfterHaversine) / $setBeforeHaversine) * 100;
    $pctReductionOsrm = (($setBeforeOsrm - $setAfterOsrm) / $setBeforeOsrm) * 100;
    
    echo "Points Handled: {$count} | Active Riders Handled: {$activeRiders} | OSRM Status: {$osrmStatus}\n";
    echo "Raw Latency (5 runs): " . implode(' ms, ', array_map(fn($t) => round($t, 2), $totalTimes)) . " ms\n";
    echo "Latency Averages: Total: " . round($avgTotal, 3) . " ms (Min: " . round($minTotal, 3) . " ms, Max: " . round($maxTotal, 3) . " ms)\n";
    echo "  - Voronoi Allocation: " . round($avgAlloc, 3) . " ms\n";
    echo "  - Route Clustering & Sequencing: " . round($avgRoute, 3) . " ms\n";
    
    echo "\nDistance Metrics (Haversine Straight-Line):\n";
    echo "  - Random Order (Before): " . round($setBeforeHaversine, 2) . " km\n";
    echo "  - Nearest-Neighbor + 2-Opt (After): " . round($setAfterHaversine, 2) . " km\n";
    echo "  - Distance Reduction: " . round($pctReductionHaversine, 2) . "%\n";
    
    echo "\nDistance Metrics (OSRM Real Driving Road Network):\n";
    echo "  - Random Order (Before): " . round($setBeforeOsrm, 2) . " km\n";
    echo "  - Nearest-Neighbor + 2-Opt (After): " . round($setAfterOsrm, 2) . " km\n";
    echo "  - Distance Reduction: " . round($pctReductionOsrm, 2) . "%\n";
    
    echo "\nVoronoi Partitioning Spatial Impact (Cross-Borough vs Zoned):\n";
    echo "  - Unzoned Cross-Borough Hub Assignment: " . round($nonVoronoiTotalKm, 2) . " km\n";
    echo "  - Voronoi Partitioned Hub Assignment: " . round($voronoiTotalKm, 2) . " km\n";
    echo "  - Cross-Hub Mileage Eliminated: " . round($voronoiSavingsPct, 2) . "%\n\n";
    
    $results[] = [
        'set_number' => $setNum,
        'points_count' => $count,
        'riders_count' => $activeRiders,
        'osrm_status' => $osrmStatus,
        'timing' => [
            'raw_runs_ms' => $totalTimes,
            'avg_total_ms' => $avgTotal,
            'min_total_ms' => $minTotal,
            'max_total_ms' => $maxTotal,
            'avg_alloc_ms' => $avgAlloc,
            'avg_route_ms' => $avgRoute,
        ],
        'haversine' => [
            'before_km' => $setBeforeHaversine,
            'after_km' => $setAfterHaversine,
            'reduction_pct' => $pctReductionHaversine
        ],
        'osrm' => [
            'before_km' => $setBeforeOsrm,
            'after_km' => $setAfterOsrm,
            'reduction_pct' => $pctReductionOsrm
        ],
        'voronoi_spatial' => [
            'unzoned_km' => $nonVoronoiTotalKm,
            'voronoi_km' => $voronoiTotalKm,
            'savings_pct' => $voronoiSavingsPct
        ],
        'rider_breakdown' => $riderBreakdown
    ];
}

// Compute aggregate stats across 5 sets
$havReductions = array_column(array_column($results, 'haversine'), 'reduction_pct');
$osrmReductions = array_column(array_column($results, 'osrm'), 'reduction_pct');
$voronoiSavings = array_column(array_column($results, 'voronoi_spatial'), 'savings_pct');
$totalLatencies = array_column(array_column($results, 'timing'), 'avg_total_ms');

echo "========================================================================================\n";
echo "EXECUTIVE SUMMARY ACROSS ALL 5 BENCHMARK SETS (30 to 50 DELIVERY POINTS):\n";
echo "========================================================================================\n";
echo "1. NEAREST-NEIGHBOR ROUTE DISTANCE REDUCTION (OSRM REAL ROAD NETWORK):\n";
echo "   Average Reduction: " . round(array_sum($osrmReductions) / count($osrmReductions), 2) . "%\n";
echo "   Minimum Reduction: " . round(min($osrmReductions), 2) . "%\n";
echo "   Maximum Reduction: " . round(max($osrmReductions), 2) . "%\n\n";

echo "2. NEAREST-NEIGHBOR ROUTE DISTANCE REDUCTION (HAVERSINE STRAIGHT-LINE):\n";
echo "   Average Reduction: " . round(array_sum($havReductions) / count($havReductions), 2) . "%\n";
echo "   Minimum Reduction: " . round(min($havReductions), 2) . "%\n";
echo "   Maximum Reduction: " . round(max($havReductions), 2) . "%\n\n";

echo "3. VORONOI SPATIAL PARTITIONING IMPACT (CROSS-BOROUGH ELIMINATION):\n";
echo "   Average Mileage Saved: " . round(array_sum($voronoiSavings) / count($voronoiSavings), 2) . "%\n";
echo "   Minimum Mileage Saved: " . round(min($voronoiSavings), 2) . "%\n";
echo "   Maximum Mileage Saved: " . round(max($voronoiSavings), 2) . "%\n\n";

echo "4. DISPATCH ENGINE COMPUTATION LATENCY (ALLOCATION + ROUTE OPTIMIZATION):\n";
echo "   Average Compute Time: " . round(array_sum($totalLatencies) / count($totalLatencies), 3) . " ms\n";
echo "   Minimum Compute Time: " . round(min($totalLatencies), 3) . " ms\n";
echo "   Maximum Compute Time: " . round(max($totalLatencies), 3) . " ms\n";
echo "========================================================================================\n";

// Save JSON artifact
file_put_contents(__DIR__ . '/benchmark_results.json', json_encode([
    'master_seed' => $masterSeed,
    'sets' => $results,
    'aggregates' => [
        'osrm_reduction_pct' => [
            'avg' => array_sum($osrmReductions) / count($osrmReductions),
            'min' => min($osrmReductions),
            'max' => max($osrmReductions)
        ],
        'haversine_reduction_pct' => [
            'avg' => array_sum($havReductions) / count($havReductions),
            'min' => min($havReductions),
            'max' => max($havReductions)
        ],
        'voronoi_spatial_savings_pct' => [
            'avg' => array_sum($voronoiSavings) / count($voronoiSavings),
            'min' => min($voronoiSavings),
            'max' => max($voronoiSavings)
        ],
        'dispatch_latency_ms' => [
            'avg' => array_sum($totalLatencies) / count($totalLatencies),
            'min' => min($totalLatencies),
            'max' => max($totalLatencies)
        ]
    ]
], JSON_PRETTY_PRINT));

echo "Saved complete dataset to benchmarks/benchmark_results.json\n";
