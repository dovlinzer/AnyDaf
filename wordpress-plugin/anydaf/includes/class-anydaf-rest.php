<?php
/**
 * WordPress REST API endpoints for AnyDaf.
 *
 * GET /wp-json/anydaf/v1/index
 *   Returns the full episode index (tractate → daf → URL map).
 *
 * GET /wp-json/anydaf/v1/stream?track_id=NNN
 *   Resolves a SoundCloud track ID to a signed CDN URL.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class AnyDaf_REST {

    const NAMESPACE = 'anydaf/v1';

    public static function register_routes() {
        register_rest_route(
            self::NAMESPACE,
            '/index',
            array(
                'methods'             => WP_REST_Server::READABLE,
                'callback'            => array( __CLASS__, 'get_index' ),
                'permission_callback' => '__return_true',
            )
        );

        register_rest_route(
            self::NAMESPACE,
            '/stream',
            array(
                'methods'             => WP_REST_Server::READABLE,
                'callback'            => array( __CLASS__, 'get_stream' ),
                'permission_callback' => '__return_true',
                'args'                => array(
                    'track_id' => array(
                        'required'          => true,
                        'validate_callback' => function( $param ) {
                            return ctype_digit( (string) $param );
                        },
                        'sanitize_callback' => 'sanitize_text_field',
                    ),
                ),
            )
        );
    }

    /**
     * GET /wp-json/anydaf/v1/index
     */
    public static function get_index( WP_REST_Request $request ) {
        $index = AnyDaf_Feed::get_index();
        return rest_ensure_response( $index );
    }

    /**
     * GET /wp-json/anydaf/v1/stream?track_id=NNN
     */
    public static function get_stream( WP_REST_Request $request ) {
        $track_id = $request->get_param( 'track_id' );
        $url      = AnyDaf_Stream::resolve( $track_id );

        if ( ! $url ) {
            return new WP_REST_Response(
                array( 'error' => 'Could not resolve stream URL.' ),
                502
            );
        }

        return rest_ensure_response( array( 'url' => $url ) );
    }
}
