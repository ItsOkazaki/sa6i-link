import { useEffect, useState } from 'react';
import ShinyText from './components/ShinyText';
import MagicBento from './components/reactbits/MagicBento';
import CodeSlots from './components/reactbits/CodeSlots';
import WarmTooltip from './components/reactbits/WarmTooltip';
import TechText from './components/reactbits/TechText';
import GradualBlur from './components/reactbits/GradualBlur';
import TargetCursor from './components/reactbits/TargetCursor';

const features = [
  { title: 'See the bigger picture.', description: 'Bring your phone screen to your computer and keep it within reach.', label: '01 / SCREEN', icon: '▣', visual: null },
  { title: 'Move things along.', description: 'Send files between your phone and PC without breaking your stride.', label: '02 / FILES', icon: '⇄', visual: null },
  { title: 'Stay in the moment.', description: 'Interact with your phone from your computer, all in one place.', label: '03 / CONTROL', icon: '⌘', visual: null }
];

function PlatformIcon({ platform }) {
  return platform === 'windows' ? <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M2 3h9v8H2zm10 0h10v8H12zM2 12h9v9H2zm10 0h10v9H12z" /></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m7.2 4.4-1-1.8a.45.45 0 0 1 .78-.45l1.04 1.9a10.3 10.3 0 0 1 7.96 0l1.04-1.9a.45.45 0 0 1 .78.45l-1 1.8A9.2 9.2 0 0 1 21 11H3a9.2 9.2 0 0 1 4.2-6.6ZM3 12h18v5.3A2.7 2.7 0 0 1 18.3 20h-.8v1.1a1 1 0 0 1-2 0V20h-7v1.1a1 1 0 0 1-2 0V20h-.8A2.7 2.7 0 0 1 3 17.3V12Zm5-3.5a.8.8 0 1 0 0-1.6.8.8 0 0 0 0 1.6Zm8 0a.8.8 0 1 0 0-1.6.8.8 0 0 0 0 1.6Z" /></svg>;
}

function Brand() {
  return <a className="brand cursor-target" href="#top" aria-label="Sa6i Link home"><span className="brand-mark" aria-hidden="true">↗</span> Sa6i<span>Link</span><i>.</i></a>;
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [enhanced, setEnhanced] = useState(false);
  const [motionAllowed, setMotionAllowed] = useState(false);
  useEffect(() => {
    setEnhanced(typeof ResizeObserver !== 'undefined' && typeof IntersectionObserver !== 'undefined' && typeof window.matchMedia === 'function');
    if (!window.matchMedia) return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setMotionAllowed(!query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);
  return (
    <div className="site-shell">
      {enhanced && motionAllowed && <TargetCursor targetSelector=".cursor-target" hideDefaultCursor={false} showLabel={false} cursorColor="#c8b5ff" />}
      <header className="header wrap">
        <Brand />
        <button className="menu-toggle cursor-target" aria-expanded={menuOpen} aria-controls="site-nav" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? 'Close' : 'Menu'} <span aria-hidden="true">{menuOpen ? '×' : '☰'}</span></button>
        <nav id="site-nav" className={menuOpen ? 'is-open' : ''} aria-label="Main navigation">
          <a className="cursor-target" href="#features" onClick={() => setMenuOpen(false)}>Features</a><a className="cursor-target" href="#setup" onClick={() => setMenuOpen(false)}>Getting started</a><a href="#downloads" className="nav-cta cursor-target" onClick={() => setMenuOpen(false)}>Get the app <span aria-hidden="true">↗</span></a>
        </nav>
      </header>

      <main id="top">
        <section className="hero wrap" aria-labelledby="hero-title">
          <div className="hero-copy">
            <div className="eyebrow"><span className="live-dot"></span> MADE FOR YOUR EVERYDAY FLOW</div>
            <h1 id="hero-title" className="masked-heading">Your devices,<br /><em><ShinyText text="in sync." color="#ad98ff" shineColor="#f8f4ff" speed={4} /></em></h1>
            <p className="intro">Your phone and PC work better together. Bring your screen, files, and everyday moments a little closer.</p>
            <div className="hero-actions"><a className="button primary cursor-target" href="#downloads">Get Sa6i Link <span aria-hidden="true">↗</span></a><a className="text-link cursor-target" href="#features">See what it does <span aria-hidden="true">↓</span></a></div>
            <div className="hero-note"><span className="orb">✳</span><span>One connection.<br /><strong>A little more seamless.</strong></span></div>
          </div>
          <div className="hero-art">
            <div className="glow"></div><div className="aero-shards" aria-hidden="true"><i></i><i></i><i></i></div>
            <div className="electric-logo"><img src="/sa6i-link.png" alt="Sa6i Link phone and computer logo" /></div>
            <div className="art-chip"><span className="chip-dot"></span> PHONE <span className="chip-line"></span> PC <span className="chip-icon">✳</span></div>
            <span className="art-index">01 / CONNECTED BY DESIGN</span>
          </div>
        </section>
        <div className="ticker" aria-hidden="true"><div>MADE TO CONNECT <span>✳</span> YOUR PHONE + YOUR PC <span>✳</span> LESS SWITCHING, MORE DOING <span>✳</span> MADE TO CONNECT <span>✳</span> YOUR PHONE + YOUR PC <span>✳</span> LESS SWITCHING, MORE DOING <span>✳</span></div></div>
        <section id="features" className="features wrap section" aria-labelledby="features-title">
          <div className="section-head"><div><p className="kicker">THE LITTLE THINGS ADD UP <span>✳</span></p><h2 id="features-title">A closer connection.<br /><em>A smoother day.</em></h2></div><p>Bring the things you need across your devices, without losing your flow.</p></div>
          {enhanced ? <MagicBento items={features} columns={3} rowHeight={290} radius={12} glowColor="#ad98ff" enableTilt={motionAllowed} intro={false} disableAnimations={!motionAllowed} className="feature-bento" /> : <div className="feature-grid">{features.map(item => <article className="feature-card" key={item.label}><span className="feature-number">{item.label}</span><div className="feature-icon">{item.icon}</div><h3>{item.title}</h3><p>{item.description}</p></article>)}</div>}
          <p className="small-note">Features and compatibility still need testing on real devices.</p>
        </section>
        <section id="setup" className="setup section"><div className="wrap setup-grid"><div><p className="kicker">LET’S GET YOU CONNECTED <span>✳</span></p><h2>Two devices.<br /><em>One simple setup.</em></h2><p className="setup-copy">Get the apps, open both devices, and follow the pairing steps on screen.</p><a className="text-link light-link cursor-target" href="#downloads">Choose your download <span aria-hidden="true">↗</span></a></div><div className="steps"><div className="step"><span>01</span><div><h3>Get the apps</h3><p>Download the Windows ZIP and Android APK below.</p></div></div><div className="step"><span>02</span><div><h3>Open on both devices</h3><p>Extract the entire Windows ZIP to a separate folder. Install the APK on your phone.</p></div></div><div className="step"><span>03</span><div><h3>Pair and explore</h3><p>Follow the in-app instructions to connect your devices.</p></div></div></div></div></section>
        <section className="connection-preview wrap section" aria-labelledby="preview-title">
          <div><p className="kicker">A LITTLE CLOSER <span>✳</span></p><h2 id="preview-title">Made to feel<br /><em>connected.</em></h2><p className="preview-copy">A simple preview of the connection experience. Follow the instructions in the apps to pair your devices.</p><div className="tech-word" aria-hidden="true">{enhanced && motionAllowed ? <TechText text="SA6I LINK" fontSize={44} color="#bba5ff" accentColor="#e9dfff" labels={false} draggable={false} selection={false} sweep={false} /> : <span>SA6I LINK</span>}</div></div>
          <div className="phone-stage scroll-expand"><div className="phone-preview glass-surface"><div className="phone-top"><span>SA6I LINK</span>{enhanced ? <WarmTooltip content="Illustration only — follow the instructions in the apps to connect." surfaceColor="#f5dfc6" inkColor="#36231e"><button className="info-button cursor-target" aria-label="About this phone preview">i</button></WarmTooltip> : <button className="info-button" title="Illustration only — follow the instructions in the apps to connect." aria-label="Illustration only — follow the instructions in the apps to connect.">i</button>}</div><div className="phone-screen"><div className="phone-symbol">↗</div><strong>Your devices, together.</strong><p>Everything you need, a little closer.</p><span className="phone-pill">PHONE + PC</span></div>{enhanced && <GradualBlur position="bottom" height="3rem" strength={1} layers={4} tint="#191329" />}</div><div className="code-demo glass-surface"><div><strong>Connection code</strong><span>Interactive example only</span></div><CodeSlots length={4} ariaLabel="Example connection code" slotSize={37} gap={6} accentColor="#bda8ff" inkColor="#ede6ff" slotColor="#30283e" digitColor="#211630" /></div></div>
        </section>
        <section id="downloads" className="download wrap section" aria-labelledby="download-title"><div className="download-top"><div><p className="kicker">READY WHEN YOU ARE <span>✳</span></p><h2 id="download-title">Let’s bring it<br /><em>all together.</em></h2></div><p>Get Sa6i Link for both your computer and your phone.</p></div>
          <div className="download-grid">
            <article className="download-card glass-surface"><div className="download-card-head"><span className="platform-icon"><PlatformIcon platform="windows" /></span></div><h3>For Windows</h3><p>App folder · ZIP · 64-bit</p><a className="button download-button cursor-target" href="https://github.com/ItsOkazaki/sa6i-link-public/releases/download/download/Sa6i.Link.zip" target="_blank" rel="noopener noreferrer">Download Windows ZIP <span aria-hidden="true">↓</span></a><small>Not an installer. Extract to a separate folder; keep your original as a backup.</small></article>
            <article className="download-card glass-surface"><div className="download-card-head"><span className="platform-icon"><PlatformIcon platform="android" /></span></div><h3>For Android</h3><p>Android app · APK</p><a className="button download-button cursor-target" href="https://github.com/ItsOkazaki/sa6i-link-public/releases/download/download/Sa6i.Link.apk" target="_blank" rel="noopener noreferrer">Download Android APK <span aria-hidden="true">↓</span></a><small>Open the downloaded APK on your phone and follow Android’s install prompts.</small></article>
          </div>
          <p className="download-help">Downloads are hosted on GitHub. Your browser or device may ask you to confirm the download or installation. If a download doesn’t start, <a className="release-link" href="https://github.com/ItsOkazaki/sa6i-link-public/releases/tag/download" target="_blank" rel="noopener noreferrer">open the downloads page ↗</a>.</p>
        </section>
      </main>
      <footer className="footer wrap"><Brand /><p>Better together, by design.</p><a className="cursor-target" href="#top">BACK TO TOP ↑</a></footer>
    </div>
  );
}
