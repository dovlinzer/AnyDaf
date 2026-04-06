<?php
/**
 * Episode index builder — PHP port of build-episodes.py / FeedManager.fetchAll().
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class AnyDaf_Feed {

    const FEED_BASE = 'https://feeds.soundcloud.com/users/soundcloud:users:958779193/sounds.rss';

    /**
     * Return the full episode index, using transient cache when available.
     *
     * @return array  { tractate: { "daf": url } }
     */
    public static function get_index() {
        $cached = get_transient( ANYDAF_TRANSIENT_KEY );
        if ( false !== $cached ) {
            return $cached;
        }

        // First build can take a while — allow up to 2 minutes.
        if ( function_exists( 'set_time_limit' ) ) {
            set_time_limit( 120 );
        }

        $index = self::build_index();
        set_transient( ANYDAF_TRANSIENT_KEY, $index, ANYDAF_CACHE_TTL );
        return $index;
    }

    /**
     * Build the episode index from scratch (RSS + playlists).
     */
    private static function build_index() {
        $index = array();

        // Phase 1: RSS feed (most recent ~1,200 episodes; direct MP3 URLs).
        $url  = self::FEED_BASE;
        $page = 0;
        while ( $url ) {
            $page++;
            $body = self::http_get( $url );
            if ( is_wp_error( $body ) || empty( $body ) ) {
                break;
            }

            // Suppress XML warnings from the feed.
            $prev = libxml_use_internal_errors( true );
            $xml  = simplexml_load_string( $body );
            libxml_use_internal_errors( $prev );
            if ( ! $xml ) {
                break;
            }

            foreach ( $xml->channel->item as $item ) {
                $title  = (string) $item->title;
                $enc    = $item->enclosure;
                if ( ! $enc ) {
                    continue;
                }
                $audio_url = (string) $enc['url'];
                if ( ! $audio_url ) {
                    continue;
                }
                $parsed = self::parse_title( $title );
                if ( ! $parsed ) {
                    continue;
                }
                list( $tractate, $daf ) = $parsed;
                if ( ! isset( $index[ $tractate ] ) ) {
                    $index[ $tractate ] = array();
                }
                if ( ! isset( $index[ $tractate ][ (string) $daf ] ) ) {
                    $index[ $tractate ][ (string) $daf ] = $audio_url;
                }
            }

            // Find next page via atom:link[@rel="next"].
            $url = null;
            $xml->registerXPathNamespace( 'atom', 'http://www.w3.org/2005/Atom' );
            $next_links = $xml->xpath( '//atom:link[@rel="next"]' );
            if ( $next_links ) {
                $href = (string) $next_links[0]['href'];
                if ( $href ) {
                    $url = $href;
                }
            }
        }

        // Phase 2: SoundCloud playlist API — fills in dafs missing from RSS.
        foreach ( ANYDAF_PLAYLIST_IDS as $tractate => $playlist_id ) {
            $dafs = self::fetch_playlist( $tractate, $playlist_id );
            if ( ! isset( $index[ $tractate ] ) ) {
                $index[ $tractate ] = array();
            }
            foreach ( $dafs as $daf => $url ) {
                // Don't overwrite RSS direct-MP3 URLs.
                if ( ! isset( $index[ $tractate ][ (string) $daf ] ) ) {
                    $index[ $tractate ][ (string) $daf ] = $url;
                }
            }
        }

        return $index;
    }

    /**
     * Fetch one SoundCloud playlist and return { daf: "soundcloud-track://TRACKID" }.
     *
     * @param string $tractate
     * @param int    $playlist_id
     * @return array
     */
    private static function fetch_playlist( $tractate, $playlist_id ) {
        $dafs = array();
        $client_id = ANYDAF_SC_CLIENT_ID;

        $body = self::http_get(
            "https://api-v2.soundcloud.com/playlists/{$playlist_id}?client_id={$client_id}"
        );
        if ( is_wp_error( $body ) || empty( $body ) ) {
            return $dafs;
        }

        $json = json_decode( $body, true );
        if ( ! isset( $json['tracks'] ) || ! is_array( $json['tracks'] ) ) {
            return $dafs;
        }

        $tracks     = $json['tracks'];
        $full       = array();
        $stub_ids   = array();

        foreach ( $tracks as $t ) {
            if ( isset( $t['title'] ) ) {
                $full[] = $t;
            } elseif ( isset( $t['id'] ) ) {
                $stub_ids[] = (int) $t['id'];
            }
        }

        // Batch-fetch stubs 50 at a time.
        foreach ( array_chunk( $stub_ids, 50 ) as $batch ) {
            $ids_param  = implode( ',', $batch );
            $batch_body = self::http_get(
                "https://api-v2.soundcloud.com/tracks?ids={$ids_param}&client_id={$client_id}"
            );
            if ( ! is_wp_error( $batch_body ) && $batch_body ) {
                $batch_tracks = json_decode( $batch_body, true );
                if ( is_array( $batch_tracks ) ) {
                    $full = array_merge( $full, $batch_tracks );
                }
            }
        }

        foreach ( $full as $track ) {
            if ( empty( $track['title'] ) || empty( $track['urn'] ) ) {
                continue;
            }
            $parsed = self::parse_title( $track['title'] );
            if ( ! $parsed ) {
                continue;
            }
            list( , $daf ) = $parsed;
            $urn_parts = explode( ':', $track['urn'] );
            $track_id  = end( $urn_parts );
            if ( ! $track_id ) {
                continue;
            }
            if ( ! isset( $dafs[ (string) $daf ] ) ) {
                $dafs[ (string) $daf ] = "soundcloud-track://{$track_id}";
            }
        }

        return $dafs;
    }

    /**
     * Parse a feed/track title into [tractate, daf_int].
     * Handles titles like "Menachot 48 (5786)" or "Bava Batra 113 (5785)".
     *
     * @param  string $title
     * @return array|null  [canonical_tractate, daf_int] or null on failure.
     */
    private static function parse_title( $title ) {
        // Strip optional year suffix "(NNNN)".
        $cleaned = trim( preg_replace( '/\s*\(\d+\)\s*$/', '', $title ) );

        $parts = preg_split( '/\s+/', $cleaned );
        if ( count( $parts ) < 2 ) {
            return null;
        }

        // Last token is the daf (may have trailing a/b suffix like "29b").
        $last = end( $parts );
        if ( ! preg_match( '/^(\d+)/', $last, $m ) ) {
            return null;
        }
        $daf = (int) $m[1];
        if ( $daf <= 0 ) {
            return null;
        }

        array_pop( $parts );
        $feed_name = implode( ' ', $parts );

        $canonical = self::canonical_tractate( $feed_name );
        if ( ! $canonical ) {
            return null;
        }

        return array( $canonical, $daf );
    }

    /**
     * Map a feed tractate name to the canonical name used in ANYDAF_TRACTATES.
     *
     * @param  string $feed_name
     * @return string|null
     */
    private static function canonical_tractate( $feed_name ) {
        // Lowercase + strip all apostrophe variants.
        $lower = strtolower( $feed_name );
        $lower = str_replace( array( "'", "\xe2\x80\x98", "\xe2\x80\x99" ), '', $lower );
        $lower = trim( $lower );

        if ( isset( ANYDAF_FEED_TO_CANONICAL[ $lower ] ) ) {
            return ANYDAF_FEED_TO_CANONICAL[ $lower ];
        }

        // Linear scan of canonical tractate list.
        foreach ( ANYDAF_TRACTATES as $t ) {
            $canon_lower = strtolower( $t['name'] );
            $canon_lower = str_replace( array( "'", "\xe2\x80\x98", "\xe2\x80\x99" ), '', $canon_lower );
            if ( $canon_lower === $lower ) {
                return $t['name'];
            }
        }

        return null;
    }

    /**
     * Thin wrapper around wp_remote_get() with a generous timeout.
     *
     * @param  string $url
     * @return string|WP_Error  Response body on success.
     */
    private static function http_get( $url ) {
        $response = wp_remote_get( $url, array( 'timeout' => 20 ) );
        if ( is_wp_error( $response ) ) {
            return $response;
        }
        return wp_remote_retrieve_body( $response );
    }
}
