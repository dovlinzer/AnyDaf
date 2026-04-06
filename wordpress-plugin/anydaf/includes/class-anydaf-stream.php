<?php
/**
 * SoundCloud stream URL resolver — PHP port of proxy-worker.js.
 *
 * Performs the two-step SoundCloud API dance to obtain a signed CDN URL
 * for a given track ID, without involving the browser (avoids CORS).
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class AnyDaf_Stream {

    /**
     * Resolve a SoundCloud track ID to a playable CDN URL.
     *
     * Step 1: fetch track metadata → extract track_authorization JWT
     *         and the progressive (MP3) transcoding URL.
     * Step 2: fetch the transcoding URL with auth appended → get signed CDN URL.
     *
     * @param  string $track_id  Numeric track ID (digits only, already validated by caller).
     * @return string|null       CDN URL string, or null on any failure.
     */
    public static function resolve( $track_id ) {
        $client_id = ANYDAF_SC_CLIENT_ID;

        // Step 1: track metadata.
        $response = wp_remote_get(
            "https://api-v2.soundcloud.com/tracks/{$track_id}?client_id={$client_id}",
            array( 'timeout' => 20 )
        );
        if ( is_wp_error( $response ) ) {
            return null;
        }

        $track = json_decode( wp_remote_retrieve_body( $response ), true );
        if ( ! is_array( $track ) ) {
            return null;
        }

        $auth         = isset( $track['track_authorization'] ) ? $track['track_authorization'] : '';
        $transcodings = isset( $track['media']['transcodings'] ) ? $track['media']['transcodings'] : array();

        // Prefer progressive (direct MP3) over HLS.
        $tc_url = null;
        foreach ( $transcodings as $t ) {
            if ( isset( $t['format']['protocol'] ) && $t['format']['protocol'] === 'progressive' ) {
                $tc_url = $t['url'];
                break;
            }
        }

        if ( ! $tc_url ) {
            return null;
        }

        // Step 2: resolve transcoding URL → signed CDN URL.
        $resolve_url = add_query_arg(
            array(
                'client_id'           => $client_id,
                'track_authorization' => $auth,
            ),
            $tc_url
        );

        $stream_response = wp_remote_get( $resolve_url, array( 'timeout' => 20 ) );
        if ( is_wp_error( $stream_response ) ) {
            return null;
        }

        $stream_data = json_decode( wp_remote_retrieve_body( $stream_response ), true );
        if ( empty( $stream_data['url'] ) ) {
            return null;
        }

        return $stream_data['url'];
    }
}
