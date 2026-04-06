<?php
/**
 * [anydaf] shortcode — enqueues assets and renders the HTML player shell.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class AnyDaf_Shortcode {

    /**
     * Shortcode callback.  Returns the player HTML.
     *
     * @param  array $atts  Shortcode attributes (unused for now).
     * @return string
     */
    public static function render( $atts ) {
        self::enqueue_assets();

        // Build the tractates array for JS (name, start, end).
        $tractates_js = array();
        foreach ( ANYDAF_TRACTATES as $t ) {
            $tractates_js[] = array(
                'name'  => $t['name'],
                'start' => (int) $t['start'],
                'end'   => (int) $t['end'],
            );
        }

        wp_localize_script(
            'anydaf-player',
            'AnyDafConfig',
            array(
                'restBase' => rest_url( 'anydaf/v1/' ),
                'pagesUrl' => ANYDAF_URL . 'assets/pages.json',
                'tractates'=> $tractates_js,
            )
        );

        ob_start();
        ?>
<div class="anydaf-player">

  <div class="anydaf-header">
    <div class="anydaf-title">AnyDaf</div>
    <div class="anydaf-subtitle">Daf Yomi with Rabbi Dov Linzer</div>
  </div>

  <div class="anydaf-body">

    <div class="anydaf-pickers">
      <div class="anydaf-picker-group anydaf-tractate-group">
        <label for="anydaf-tractate-sel">Tractate</label>
        <div class="anydaf-picker-wrap">
          <select id="anydaf-tractate-sel"></select>
        </div>
      </div>
      <div class="anydaf-picker-group anydaf-daf-group">
        <label for="anydaf-daf-sel">Daf</label>
        <div class="anydaf-picker-wrap">
          <select id="anydaf-daf-sel"></select>
        </div>
      </div>
    </div>

    <div class="anydaf-image-section">
      <div class="anydaf-amud-toggle">
        <button class="anydaf-amud-btn anydaf-amud-active" id="anydaf-amud-a">Amud Aleph (a)</button>
        <button class="anydaf-amud-btn" id="anydaf-amud-b">Amud Bet (b)</button>
      </div>
      <div class="anydaf-image-wrap">
        <img id="anydaf-page-img" src="" alt="" style="display:none;">
        <div id="anydaf-no-image" class="anydaf-no-image" style="display:none;">No image available for this tractate.</div>
      </div>
    </div>

    <button class="anydaf-play-btn" id="anydaf-play-btn" disabled>
      <svg id="anydaf-play-icon" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5v14l11-7z"/>
      </svg>
      <span id="anydaf-play-label">Play</span>
    </button>

    <div class="anydaf-progress-wrap" id="anydaf-progress-wrap">
      <div class="anydaf-progress-track" id="anydaf-progress-track">
        <div class="anydaf-progress-fill" id="anydaf-progress-fill"></div>
      </div>
      <div class="anydaf-progress-times">
        <span id="anydaf-time-cur">0:00</span>
        <span id="anydaf-time-tot">0:00</span>
      </div>
    </div>

    <div class="anydaf-status" id="anydaf-status">
      <span class="anydaf-spinner"></span> Loading episodes&hellip;
    </div>

  </div><!-- .anydaf-body -->

</div><!-- .anydaf-player -->

<audio id="anydaf-audio" preload="none"></audio>
        <?php
        return ob_get_clean();
    }

    /**
     * Enqueue CSS and JS.  Safe to call multiple times (WP deduplicates).
     */
    public static function enqueue_assets() {
        wp_enqueue_style(
            'anydaf-player',
            ANYDAF_URL . 'assets/anydaf.css',
            array(),
            ANYDAF_VERSION
        );

        wp_enqueue_script(
            'anydaf-player',
            ANYDAF_URL . 'assets/anydaf.js',
            array(),
            ANYDAF_VERSION,
            true  // load in footer
        );
    }
}
