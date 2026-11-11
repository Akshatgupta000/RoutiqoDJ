<?php
// count_loc.php - Counts lines of code excluding node_modules, vendor, .git, dist, etc.

$rootDir = realpath(__DIR__ . '/..');

$excludeDirs = [
    'node_modules',
    'vendor',
    '.git',
    'dist',
    'storage',
    'benchmarks', // our newly added benchmarks folder
    '.system_generated',
];

$validExtensions = [
    'php', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'json', 'vue'
];

$stats = [
    'by_extension' => [],
    'by_directory' => [
        'Backend' => 0,
        'Dashboard' => 0,
        'Landing' => 0,
        'Root' => 0
    ],
    'total_lines' => 0,
    'total_files' => 0
];

function shouldExclude($path, $excludeDirs) {
    foreach ($excludeDirs as $dir) {
        if (strpos($path, DIRECTORY_SEPARATOR . $dir . DIRECTORY_SEPARATOR) !== false ||
            strpos($path, DIRECTORY_SEPARATOR . $dir) === (strlen($path) - strlen(DIRECTORY_SEPARATOR . $dir))) {
            return true;
        }
    }
    return false;
}

$iterator = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($rootDir, RecursiveDirectoryIterator::SKIP_DOTS)
);

foreach ($iterator as $file) {
    $path = $file->getPathname();
    if (shouldExclude($path, $excludeDirs)) {
        continue;
    }
    
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    if (!in_array($ext, $validExtensions)) {
        continue;
    }
    
    // Don't count package-lock.json or composer.lock as code lines (standard practice, but let's record if requested)
    if (in_array(basename($path), ['package-lock.json', 'composer.lock'])) {
        continue;
    }
    
    $lines = count(file($path, FILE_IGNORE_NEW_LINES));
    $stats['total_lines'] += $lines;
    $stats['total_files']++;
    
    $stats['by_extension'][$ext] = ($stats['by_extension'][$ext] ?? 0) + $lines;
    
    $rel = substr($path, strlen($rootDir) + 1);
    $parts = explode(DIRECTORY_SEPARATOR, $rel);
    $topDir = $parts[0];
    if (isset($stats['by_directory'][$topDir])) {
        $stats['by_directory'][$topDir] += $lines;
    } else {
        $stats['by_directory']['Root'] += $lines;
    }
}

echo json_encode($stats, JSON_PRETTY_PRINT);
