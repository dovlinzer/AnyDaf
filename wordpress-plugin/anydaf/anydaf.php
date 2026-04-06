<?php
/**
 * Plugin Name: AnyDaf
 * Plugin URI:  https://github.com/linzer/anydaf
 * Description: Embeds a Daf Yomi audio player (YCT / Rabbi Dov Linzer) via the [anydaf] shortcode.
 * Version:     1.0.0
 * Author:      Rabbi Dov Linzer
 * License:     GPL-2.0+
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// ── Constants ──────────────────────────────────────────────────────────────────
define( 'ANYDAF_VERSION',      '1.0.0' );
define( 'ANYDAF_DIR',          plugin_dir_path( __FILE__ ) );
define( 'ANYDAF_URL',          plugin_dir_url( __FILE__ ) );
define( 'ANYDAF_SC_CLIENT_ID', '1IzwHiVxAHeYKAMqN0IIGD3ZARgJy2kl' );
define( 'ANYDAF_TRANSIENT_KEY','anydaf_episode_index' );
define( 'ANYDAF_CACHE_TTL',    DAY_IN_SECONDS ); // 24 hours

// ── Includes ───────────────────────────────────────────────────────────────────
require_once ANYDAF_DIR . 'includes/anydaf-tractates.php';
require_once ANYDAF_DIR . 'includes/class-anydaf-feed.php';
require_once ANYDAF_DIR . 'includes/class-anydaf-stream.php';
require_once ANYDAF_DIR . 'includes/class-anydaf-rest.php';
require_once ANYDAF_DIR . 'includes/class-anydaf-shortcode.php';

// ── Boot ───────────────────────────────────────────────────────────────────────
add_action( 'rest_api_init', array( 'AnyDaf_REST', 'register_routes' ) );
add_shortcode( 'anydaf', array( 'AnyDaf_Shortcode', 'render' ) );
