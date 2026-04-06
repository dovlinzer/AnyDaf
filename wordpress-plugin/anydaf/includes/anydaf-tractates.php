<?php
/**
 * Tractate definitions, playlist IDs, and feed-name aliases.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// ── Ordered tractate list ──────────────────────────────────────────────────────
// Matches Tractate.swift (canonical names from allTractates).
// Ta'anit uses right single quotation mark (U+2019).
define( 'ANYDAF_TRACTATES', array(
    // Seder Zeraim
    array( 'name' => 'Berakhot',      'start' => 2,  'end' => 64  ),
    // Seder Moed
    array( 'name' => 'Shabbat',       'start' => 2,  'end' => 157 ),
    array( 'name' => 'Eiruvin',       'start' => 2,  'end' => 105 ),
    array( 'name' => 'Pesachim',      'start' => 2,  'end' => 121 ),
    array( 'name' => 'Shekalim',      'start' => 2,  'end' => 22  ),
    array( 'name' => 'Rosh Hashanah', 'start' => 2,  'end' => 35  ),
    array( 'name' => 'Yoma',          'start' => 2,  'end' => 88  ),
    array( 'name' => 'Sukkah',        'start' => 2,  'end' => 56  ),
    array( 'name' => 'Beitzah',       'start' => 2,  'end' => 40  ),
    array( 'name' => "Ta\xe2\x80\x99anit", 'start' => 2,  'end' => 31  ),
    array( 'name' => 'Megillah',      'start' => 2,  'end' => 32  ),
    array( 'name' => 'Moed Katan',    'start' => 2,  'end' => 29  ),
    array( 'name' => 'Chagigah',      'start' => 2,  'end' => 27  ),
    // Seder Nashim
    array( 'name' => 'Yevamot',       'start' => 2,  'end' => 122 ),
    array( 'name' => 'Ketubot',       'start' => 2,  'end' => 112 ),
    array( 'name' => 'Nedarim',       'start' => 2,  'end' => 91  ),
    array( 'name' => 'Nazir',         'start' => 2,  'end' => 66  ),
    array( 'name' => 'Sotah',         'start' => 2,  'end' => 49  ),
    array( 'name' => 'Gittin',        'start' => 2,  'end' => 90  ),
    array( 'name' => 'Kiddushin',     'start' => 2,  'end' => 82  ),
    // Seder Nezikin
    array( 'name' => 'Bava Kamma',    'start' => 2,  'end' => 119 ),
    array( 'name' => 'Bava Metzia',   'start' => 2,  'end' => 119 ),
    array( 'name' => 'Bava Batra',    'start' => 2,  'end' => 176 ),
    array( 'name' => 'Sanhedrin',     'start' => 2,  'end' => 113 ),
    array( 'name' => 'Makkot',        'start' => 2,  'end' => 24  ),
    array( 'name' => 'Shevuot',       'start' => 2,  'end' => 49  ),
    array( 'name' => 'Avodah Zarah',  'start' => 2,  'end' => 76  ),
    array( 'name' => 'Horayot',       'start' => 2,  'end' => 14  ),
    // Seder Kodashim
    array( 'name' => 'Zevachim',      'start' => 2,  'end' => 120 ),
    array( 'name' => 'Menachot',      'start' => 2,  'end' => 110 ),
    array( 'name' => 'Hullin',        'start' => 2,  'end' => 142 ),
    array( 'name' => 'Bekhorot',      'start' => 2,  'end' => 61  ),
    array( 'name' => 'Arakhin',       'start' => 2,  'end' => 34  ),
    array( 'name' => 'Temurah',       'start' => 2,  'end' => 34  ),
    array( 'name' => 'Keritot',       'start' => 2,  'end' => 28  ),
    array( 'name' => 'Meilah',        'start' => 2,  'end' => 22  ),
    array( 'name' => 'Kinnim',        'start' => 22, 'end' => 25  ),
    array( 'name' => 'Tamid',         'start' => 25, 'end' => 33  ),
    array( 'name' => 'Middos',        'start' => 34, 'end' => 37  ),
    // Seder Taharot
    array( 'name' => 'Niddah',        'start' => 2,  'end' => 73  ),
) );

// ── SoundCloud playlist IDs ────────────────────────────────────────────────────
// From FeedManager.swift tractatePlaylistIDs (uses canonical names from allTractates).
define( 'ANYDAF_PLAYLIST_IDS', array(
    'Berakhot'                => 1224453841,
    'Shabbat'                 => 1224957730,
    'Eiruvin'                 => 1224604675,
    'Pesachim'                => 1223731237,
    'Yoma'                    => 1224408415,
    'Sukkah'                  => 1224961240,
    'Beitzah'                 => 1224467716,
    'Rosh Hashanah'           => 1225124800,
    "Ta\xe2\x80\x99anit"     => 1947852215,
    'Moed Katan'              => 1947706063,
    'Chagigah'                => 1947633743,
    'Yevamot'                 => 1225156528,
    'Ketubot'                 => 1224649789,
    'Nedarim'                 => 1224705577,
    'Nazir'                   => 1950629151,
    'Sotah'                   => 1595841331,
    'Gittin'                  => 1224617542,
    'Kiddushin'               => 1224719668,
    'Bava Kamma'              => 1224873547,
    'Bava Metzia'             => 1224692203,
    'Bava Batra'              => 1224939157,
    'Sanhedrin'               => 1225177738,
    'Makkot'                  => 1224421891,
    'Shevuot'                 => 1954367887,
    'Avodah Zarah'            => 1224438616,
    'Horayot'                 => 1224645901,
    'Zevachim'                => 1225250722,
    'Menachot'                => 1950820791,
    'Hullin'                  => 1224735955,
    'Bekhorot'                => 1224596788,
    'Arakhin'                 => 1224424696,
    'Temurah'                 => 1225194493,
    'Meilah'                  => 1224865387,
    'Kinnim'                  => 1954771503,
    'Tamid'                   => 1954771299,
    'Niddah'                  => 1225213678,
) );

// ── Feed-name aliases → canonical names ───────────────────────────────────────
// Lowercased keys (apostrophes stripped), from RSSParser.swift feedToCanonical.
define( 'ANYDAF_FEED_TO_CANONICAL', array(
    'eruvin'        => 'Eiruvin',
    'menahot'       => 'Menachot',
    'zevachim'      => 'Zevachim',
    'taanit'        => "Ta\xe2\x80\x99anit",
    'meilah'        => 'Meilah',
    'berachot'      => 'Berakhot',
    'berachos'      => 'Berakhot',
    'brachot'       => 'Berakhot',
    'shabbos'       => 'Shabbat',
    'kesubos'       => 'Ketubot',
    'shevuos'       => 'Shevuot',
    'moed katan'    => 'Moed Katan',
    'avodah zarah'  => 'Avodah Zarah',
    'avoda zara'    => 'Avodah Zarah',
    'megilah'       => 'Megillah',
    'rosh hashana'  => 'Rosh Hashanah',
    'rosh hashanah' => 'Rosh Hashanah',
    'bava kama'     => 'Bava Kamma',
    'bava metzia'   => 'Bava Metzia',
    'bava batra'    => 'Bava Batra',
) );
