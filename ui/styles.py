"""
ui/styles.py – Netflix-inspired completely dark UI
"""

import streamlit as st

_CSS = """
<style>
/* ── Base Styling & Typography ───────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Helvetica+Neue:wght@300;400;500;700;900&display=swap');

html, body, [class*="css"], .stApp { 
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important; 
    background-color: #0B0B0C !important; 
    color: #FFFFFF !important;
    overflow-x: hidden !important; /* Prevent horizontal scroll */
}

::-webkit-scrollbar { display: none !important; }
* { -ms-overflow-style: none !important; scrollbar-width: none !important; }

/* ── Remove Streamlit Defaults ───────────────────────────────────────────── */
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
}
[data-testid="stHeader"], footer, [data-testid="collapsedControl"] { display: none !important; }

/* ── The main search button styling ──────────────────────────────────────── */
.block-container .stButton {
    display: flex !important;
    justify-content: flex-end !important;
}
/* Reset button alignment inside dialogs */
[data-testid="stModal"] .stButton,
[role="dialog"] .stButton {
    justify-content: center !important;
}
.stButton > button {
    background-color: #01b4e4 !important; /* TMDB Blue */
    color: white !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    border: none !important;
    width: auto !important;
    min-width: 140px !important;
    height: 38px !important;
    font-size: 1rem !important;
    margin-top: 32px !important; /* Level with bottom of labeled inputs */
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.stButton > button:hover {
    background-color: #0190b8 !important; /* Darker TMDB Blue */
}

/* ── Secondary / ghost buttons (nav, profile chips) ────────────────────── */
button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #888 !important;
    min-width: unset !important;
    margin-top: 0 !important;
    height: auto !important;
    min-height: 32px !important;
    font-weight: 400 !important;
    font-size: 0.88rem !important;
}
button[data-testid="baseButton-secondary"]:hover:not(:disabled) {
    background: rgba(255,255,255,0.06) !important;
    border-color: rgba(255,255,255,0.28) !important;
    color: #ccc !important;
}
button[data-testid="baseButton-secondary"]:disabled {
    opacity: 0.25 !important;
    cursor: default !important;
}

/* ── Text Input Styling (to match button height) ─────────────────────────── */
div[data-testid="stTextInput"] input {
    height: 45px !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background-color: rgba(255,255,255,0.05) !important;
}
.stButton > button * {
    color: white !important;
}

/* ── Full-Width Navigation ──────────────────────────────────────────────── */
.nav-wrapper {
    position: fixed;
    top: 0;
    left: 0; right: 0;
    width: 100%;
    z-index: 2000;
    transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s;
}
.nav-wrapper.nav-hidden {
    transform: translateY(-100%);
    opacity: 0;
}
.nav-container-full {
    background: rgba(11, 11, 12, 0.95);
    backdrop-filter: blur(15px);
    -webkit-backdrop-filter: blur(15px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0 4%;
    height: 55px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}
.nav-left {
    display: flex;
    align-items: center;
    gap: 35px;
}
.nav-link, .nav-link:visited, .nav-link:active {
    color: #FFFFFF !important;
    text-decoration: none !important;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding-top: 6px;
}
.nav-link:hover {
    color: #FFFFFF !important;
    font-weight: 500 !important;
    text-decoration: none !important;
}
.nav-link.active {
    font-weight: 600 !important;
}
.nav-link .active-dot {
    width: 5px;
    height: 5px;
    background-color: #FFFFFF;
    border-radius: 50%;
    opacity: 0;
    transition: opacity 0.3s ease;
}
.nav-link.active .active-dot {
    opacity: 1;
}
.nav-right-search {
    display: flex;
    align-items: center;
}
.nav-search-box {
    background: rgba(40, 40, 40, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 20px;
    padding: 8px 15px 8px 35px;
    color: white;
    font-size: 0.9rem;
    outline: none;
    width: 250px;
    transition: all 0.3s ease;
    background-image: url('data:image/svg+xml;utf8,<svg fill="%23999999" height="16" viewBox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>');
    background-repeat: no-repeat;
    background-position: 12px center;
}
.nav-search-box:focus {
    background: rgba(60, 60, 60, 0.8);
    border-color: #38bdf8;
    width: 300px;
}
.nav-right input:focus { border-color: #38bdf8; }

/* ── Pure CSS Auto-Rotating Hero Carousel ────────────────────────────────── */
.hero-container { position: relative; width: 100vw; height: 65vh; min-height: 480px; overflow: hidden; background: #0B0B0C; margin-bottom: -60px; }
.hero-slide {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    opacity: 0;
    background-size: cover;
    background-position: center 10%;
    background-repeat: no-repeat;
    display: flex;
    align-items: center; /* Back to centered for safety */
    padding: 0 4%;
    padding-bottom: 50px; /* Push content up slightly */
    animation: fadeCycle 200s infinite;
}

/* Keyframes for a 10-slide carousel. 20s per slide out of 200s total = 10% each.
   Visible for ~8%, crossfade over 2% */
@keyframes fadeCycle {
    0%, 8% { opacity: 1; z-index: 2; }
    10%, 98% { opacity: 0; z-index: 1; }
    100% { opacity: 1; z-index: 2; }
}

/* Fade out to black at the bottom matching the background */
.hero-fade {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(to right, #0B0B0C 15%, rgba(11,11,12,0.85) 50%, rgba(11,11,12,0) 100%),
                linear-gradient(to top, #0B0B0C 0%, rgba(11,11,12,0.4) 40%);
    z-index: 1;
    pointer-events: none;
}

.hero-content {
    position: relative;
    z-index: 10;
    display: flex;
    align-items: center;
    max-width: 60%;
}
.hero-rank {
    font-size: 11rem; /* Reduced from 14rem */
    font-weight: 900;
    line-height: 0.8;
    color: transparent;
    -webkit-text-stroke: 4px #FFFFFF;
    margin-right: 1.5rem;
    z-index: 10; float: left;
}
.hero-details {
    display: flex;
    flex-direction: column;
    z-index: 11;
}
.hero-title {
    font-size: 3.2rem; /* Reduced from 4rem */
    font-weight: 900;
    line-height: 1.1;
    margin-bottom: 1rem;
    text-transform: uppercase;
    text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
}
.hero-summary {
    font-size: 1rem; /* Reduced from 1.1rem */
    color: #D2D2D2;
    margin-bottom: 0.8rem; /* Reduced from 1rem */
    line-height: 1.3;
    text-shadow: 1px 1px 4px rgba(0,0,0,0.8);
    max-width: 90%; /* Increased width slightly to allow more text per line */
    display: -webkit-box;
    -webkit-line-clamp: 4; /* Limit to 4 lines */
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.hero-buttons { display: flex; gap: 1rem; }
.btn {
    padding: 0.6rem 2rem;
    border-radius: 4px;
    font-weight: 600;
    font-size: 1.1rem;
    cursor: pointer;
    text-decoration: none;
    text-align: center;
    transition: 0.2s;
}
.btn-primary { background: #FFFFFF; color: #000000; }
.btn-primary:hover { background: rgba(255,255,255,0.75); }
.btn-secondary { background: rgba(109,109,110,0.4); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.5); }
.btn-secondary:hover { background: rgba(109,109,110,0.7); }


/* ── Horizontal Rows General ─────────────────────────────────────────────── */
.row-section {
    padding: 0 4%;
    margin-top: 0; /* Removed margin-top */
    position: relative;
    z-index: 15;
}
/* Pull the first row up moderately */
.row-section.first-row { margin-top: -3rem; }

.row-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 1rem;
}
.row-title { 
    font-size: 1.4rem; 
    font-weight: 700; 
    color: #FFFFFF; 
    display: flex;
    align-items: center;
}
/* The Blue vertical tick mark next to section titles */
.row-title::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 1.2rem;
    background-color: #38bdf8;
    margin-right: 10px;
    border-radius: 2px;
}
.category-nav-wrapper {
    display: flex;
    align-items: center;
    position: relative;
    max-width: 45%; /* Show fewer categories at once */
    overflow: hidden;
    mask-image: linear-gradient(to right, transparent, black 10%, black 90%, transparent);
}
.category-nav {
    display: flex;
    gap: 2.5rem;
    overflow-x: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
    padding: 10px 20px;
    white-space: nowrap;
    scroll-behavior: smooth;
}
.category-nav::-webkit-scrollbar { display: none; }
.category-item {
    color: #888;
    font-size: 1.05rem;
    font-weight: 600;
    cursor: pointer;
    transition: 0.3s ease;
    position: relative;
}
.category-item:hover { color: #fff; }
.category-item.active {
    color: #fff;
    transform: scale(1.05);
}
.category-item.active::after {
    content: '';
    position: absolute;
    bottom: -6px;
    left: 0;
    right: 0;
    height: 3px;
    background: #ff9800; /* Orange Accent for tabs */
    border-radius: 20px;
    box-shadow: 0 0 10px rgba(255, 152, 0, 0.5);
}

/* Info Icon & Tooltip */
.info-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: 1.5px solid #555;
    border-radius: 50%;
    color: #999;
    font-size: 0.85rem;
    font-weight: bold;
    margin-left: 12px;
    cursor: pointer;
    position: relative;
    transition: all 0.3s;
    vertical-align: middle;
}
.info-icon:hover {
    color: #ff9800; /* Orange Accent */
    border-color: #ff9800;
    background: rgba(255, 152, 0, 0.1);
}
.info-icon .tooltip {
    visibility: hidden;
    width: 250px;
    background-color: #1a1a1a;
    color: #eee;
    text-align: left;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 12px;
    position: absolute;
    z-index: 1000;
    bottom: 150%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0;
    transition: opacity 0.3s, visibility 0.3s;
    font-size: 0.9rem;
    line-height: 1.4;
    font-weight: normal;
    pointer-events: none;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
}
.info-icon:hover .tooltip {
    visibility: visible;
    opacity: 1;
}
.info-icon .tooltip::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -8px;
    border-width: 8px;
    border-style: solid;
    border-color: #333 transparent transparent transparent;
}
.tooltip-cta {
    display: block;
    margin-top: 8px;
    color: #ff9800; /* Orange CTA */
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
}

.row-filters {
    display: flex;
    gap: 1.5rem;
    font-size: 0.95rem;
}
.row-filters span { color: #999; cursor: pointer; transition: 0.3s; }
.row-filters span:hover { color: #FFF; }
.row-filters span.active { color: #FFFFFF; border-bottom: 2px solid #38bdf8; padding-bottom: 4px; }

.carousel-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}
.scroll-btn {
    position: absolute;
    top: 0;
    bottom: 25px; /* Same as the container's padding-bottom */
    width: 60px;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border: none;
    font-size: 2.5rem;
    font-weight: 900;
    z-index: 50;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 0.3s ease;
}
.carousel-wrapper:hover .scroll-btn {
    opacity: 1;
}
.scroll-btn.left {
    left: 0;
    background: linear-gradient(to right, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 100%);
}
.scroll-btn.right {
    right: 0;
    background: linear-gradient(to left, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 100%);
}
.scroll-btn:hover {
    background-color: rgba(0,0,0,0.6);
}

.posters-container {
    display: flex;
    gap: 15px;
    overflow-x: auto;
    overflow-y: hidden;
    padding-top: 15px;
    padding-bottom: 25px;
    width: 100%;
    scroll-behavior: smooth;
}
.posters-container::-webkit-scrollbar { display: none; }
.posters-container { -ms-overflow-style: none; scrollbar-width: none; }

/* Standard Poster with Hover Overlay */
.poster-card {
    position: relative;
    flex: 0 0 16.666%; /* 6 items per view */
    min-width: 160px;
    max-width: 250px;
    transition: transform 0.3s ease;
    cursor: pointer;
}
.poster-card:hover { transform: scale(1.05); z-index: 20; }

/* ── Top 10 Specific Row (Hollow Numbers) ────────────────────────────────── */
.top10-card {
    display: flex;
    align-items: center;
    flex: 0 0 auto;
    width: clamp(220px, calc(100vw / 5.5), 300px);
    cursor: pointer;
    position: relative;
}
.top10-number {
    font-size: 10rem;
    font-weight: 900;
    color: transparent;
    -webkit-text-stroke: 2px rgba(255, 255, 255, 0.4);
    letter-spacing: -0.5rem;
    margin-right: -1.5rem;
    z-index: 1;
    line-height: 0.8;
}
.top10-img-wrap {
    width: 60%;
    z-index: 2;
    transition: transform 0.3s ease;
}
.top10-card:hover .top10-img-wrap { transform: scale(1.08); }

/* ── SQL Modal ──────────────────────────────────────────────────────────── */
.sql-modal {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
}
.sql-modal-content {
    background: #141414;
    padding: 2rem;
    border-radius: 8px;
    border: 1px solid #333;
    width: 80%;
    max-width: 800px;
    position: relative;
    box-shadow: 0 10px 40px rgba(0,0,0,0.9);
}
.sql-close-btn {
    position: absolute;
    top: 15px;
    right: 20px;
    font-size: 1.5rem;
    color: #999;
    cursor: pointer;
}
.sql-close-btn:hover { color: #FFF; }
.sql-modal pre {
    background: #000;
    padding: 1rem;
    border-radius: 4px;
    color: #38bdf8;
    font-family: monospace;
    font-size: 0.9rem;
    white-space: pre-wrap;
    max-height: 60vh;
    overflow-y: auto;
}


/* ── Search Page Styles ──────────────────────────────────────────────────── */
.search-layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 30px;
    padding: 100px 4% 40px;
}
.search-sidebar {
    display: flex;
    flex-direction: column;
    gap: 15px;
}
.filter-card {
    background: #1a1a1c;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.filter-card-header {
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding-bottom: 10px;
}
.filter-section {
    margin-top: 15px;
}
.filter-section-title {
    font-size: 0.9rem;
    color: #888;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.genre-bubble-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.genre-bubble {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}
.genre-bubble:hover, .genre-bubble.active {
    background: #01b4e4;
    border-color: #01b4e4;
    color: #fff;
}

.movie-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 30px;
}
.movie-card-search {
    background: #1a1a1c;
    border-radius: 8px;
    overflow: hidden;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    position: relative;
    border: 1px solid rgba(255,255,255,0.05);
}
.movie-card-search:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 24px rgba(0,0,0,0.5);
}
.movie-card-search img {
    width: 100%;
    height: 300px;
    object-fit: cover;
}
.movie-rating-search {
    position: absolute;
    bottom: 85px;
    left: 12px;
    width: 38px;
    height: 38px;
    background: #081c22;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #21d07a;
    font-size: 0.8rem;
    font-weight: 700;
    color: white;
    z-index: 10;
}
.movie-info-search {
    padding: 20px 12px 12px;
}
.movie-title-search {
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 4px;
    color: white;
}
.movie-date-search {
    color: #888;
    font-size: 0.9rem;
}

/* ── TMDB-Style White Card (Shared) ─────────────────────────────────────── */
.tmdb-card {
    position: relative;
    width: 100%;
    border-radius: 8px;
    overflow: visible;
    background: #ffffff !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border: 1px solid #e3e3e3;
    font-family: 'Source Sans Pro', Arial, sans-serif;
    transition: transform 0.2s ease;
}
.tmdb-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.tmdb-card-img-wrap {
    width: 100%;
    padding-top: 150%;
    position: relative;
    overflow: hidden;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
.tmdb-card-img-wrap img {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: cover;
}
.tmdb-card-info {
    padding: 26px 10px 12px 10px;
    background: #ffffff;
    text-align: left;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}
.tmdb-card-title {
    font-weight: 700;
    color: #000000 !important;
    font-size: 0.95rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 2px;
    line-height: 1.2;
    height: 2.4em; /* Approx 2 lines */
}
.tmdb-card-date {
    color: rgba(0,0,0,0.6) !important;
    font-size: 0.9rem;
}
.tmdb-rating-circle {
    position: absolute;
    bottom: 85px;
    left: 10px;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #081c22;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    z-index: 10;
}
.tmdb-rating-progress {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}
.tmdb-rating-inner {
    width: 85%;
    height: 85%;
    background: #081c22;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white !important;
    font-size: 0.9rem;
    font-weight: 700;
}

/* ── People Page Styles ──────────────────────────────────────────────────── */
.people-layout {
    padding: 100px 4% 40px;
}
.people-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 25px;
}
.person-card {
    background: #1a1a1c;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.05);
    transition: transform 0.3s;
    cursor: pointer;
}
.person-card:hover { transform: scale(1.03); }
.person-card img {
    width: 100%;
    height: 250px;
    object-fit: cover;
}
.person-info {
    padding: 12px;
}
.person-name {
    font-weight: 700;
    font-size: 1.1rem;
    margin-bottom: 4px;
}
.person-known {
    font-size: 0.9rem;
    color: #888;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Person Profile Detail */
.person-profile-container {
    padding: 100px 4% 40px;
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 50px;
}
.profile-left {
    display: flex;
    flex-direction: column;
    gap: 30px;
}
.profile-portrait {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}
.profile-portrait img {
    width: 100%;
    display: block;
}
.personal-info-card h3 {
    font-size: 1.2rem;
    margin-bottom: 15px;
    border-bottom: 1px solid #333;
    padding-bottom: 8px;
}
.info-item {
    margin-bottom: 15px;
}
.info-label {
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 2px;
}
.info-value {
    font-size: 0.95rem;
    color: #ccc;
}

.profile-right h1 {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 20px;
}
.bio-section h3 {
    font-size: 1.3rem;
    margin-bottom: 10px;
}
.bio-content {
    font-size: 1.05rem;
    line-height: 1.6;
    color: #d1d1d1;
    margin-bottom: 30px;
}
.known-for-section h3 {
    margin-bottom: 15px;
}
.known-for-scroll {
    display: flex;
    gap: 15px;
    overflow-x: auto;
    padding-bottom: 15px;
}
.known-for-item {
    flex: 0 0 150px;
    text-align: center;
}
.known-for-item img {
    width: 100%;
    border-radius: 8px;
    margin-bottom: 8px;
}
.known-for-title {
    font-size: 0.85rem;
    font-weight: 600;
}

.acting-table-container {
    margin-top: 40px;
    background: #1a1a1c;
    border-radius: 8px;
    border: 1px solid #333;
    overflow: hidden;
}
.acting-table-header {
    background: #252527;
    padding: 12px 20px;
    font-weight: 700;
    display: flex;
    justify-content: space-between;
}
.acting-row {
    padding: 12px 20px;
    border-bottom: 1px solid #333;
    display: flex;
    gap: 20px;
    align-items: center;
}
.acting-year {
    color: #888;
    width: 50px;
}
.acting-movie {
    font-weight: 600;
}
.acting-role {
    color: #aaa;
    font-size: 0.9rem;
}

/* ── SQL Tooltips & Panels ──────────────────────────────────────────────── */
.sql-panel-container {
    margin: 20px 0;
    padding: 20px;
    background: rgba(45, 45, 45, 0.4);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
}

.sql-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.sql-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #e50914;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.sql-code {
    font-family: 'Space Mono', 'Courier New', monospace;
    font-size: 0.85rem;
    color: #01b4e4;
    background: #000;
    padding: 15px;
    border-radius: 8px;
    white-space: pre-wrap;
    border: 1px solid #333;
}

.sql-trigger {
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: #e50914;
    color: white;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.3s ease;
    border: none;
    margin-bottom: 20px;
}

.sql-trigger:hover {
    background: #ff0a16;
    transform: scale(1.05);
}

/* ── Genre Bubbles Selected State ────────────────────────────────────────── */
.genre-bubble.active {
    background: #01b4e4 !important;
    color: #fff !important;
    border-color: #01b4e4 !important;
}

</style>
"""

def inject():
    st.markdown(_CSS, unsafe_allow_html=True)
    page = st.query_params.get("page", "home")
    if page in ["search", "people", "movie", "recommend"]:
        st.markdown("""
        <style>
        .block-container {
            padding-left: 4% !important;
            padding-right: 4% !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
def get_css():
    return _CSS

def get_raw_css():
    """Returns the CSS content without the enclosing <style> tags."""
    return _CSS.replace("<style>", "").replace("</style>", "")

def render_navbar(active_page="home"):
    """Renders the standard navigation bar across all pages."""
    links = [
        ("home", "Home", "/?page=home"),
        ("search", "Recherche", "/?page=search"),
        ("people", "Artistes", "/?page=people"),
        ("recommend", "Recommandations", "/?page=recommend"),
    ]
    links_html = "".join([f'<a class="nav-link {"active" if active_page == p[0] else ""}" href="{p[2]}" target="_self"><span>{p[1]}</span><div class="active-dot"></div></a>' for p in links])
    nav_html = f'<div class="nav-wrapper" id="nav-wrapper"><div class="nav-container-full"><div class="nav-left">{links_html}</div></div></div>'
    st.markdown(nav_html, unsafe_allow_html=True)

