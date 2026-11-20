// SPDX-License-Identifier: GPL-3.0-or-later
#include "qt_embed_adapter.h"

#include <QtCore/QDebug>
#include <QtCore/QtEnvironmentVariables>
#include <QtCore/QTimer>
#include <QtCore/QThread>
#include <atomic>
#include <string>
#include <utility>

#if defined(_WIN32) || defined(SA6I_EMBED_TEST)
#include "native_embed.h"
#define SA6I_HAVE_EMBED 1
#else
#define SA6I_HAVE_EMBED 0
#endif

#if SA6I_HAVE_EMBED
// The worker owns its independent host copy until finished; it never polls,
// attaches or manipulates any child HWND. The GUI thread owns the original.
class LaunchWorker final : public QThread {
public:
    LaunchWorker(const EmbedHost &source, std::wstring path, QObject *parent)
        : QThread(parent), host(source), directory(std::move(path)) {}
    EmbedHost host;
    std::atomic<bool> entered {false};
private:
    void run() override {
        entered.store(true, std::memory_order_release);
        embed_start(&host, directory.c_str());
    }
    std::wstring directory;
};
#endif

struct QtEmbedAdapter::Impl {
    QTimer timer;
    bool bound = false;
    bool lastBound = false;
    bool lastPending = false;
    bool lastTracked = false;
    QString lastStatus;
    QString lastProfile;
    quint32 lastError = 0;
#if SA6I_HAVE_EMBED
    EmbedHost host {};
    LaunchWorker *worker = nullptr;
    bool closeDuringLaunch = false;
#endif
};

QtEmbedAdapter::QtEmbedAdapter(QObject *parent) : QObject(parent), d(new Impl)
{
    d->timer.setParent(this);
    d->timer.setInterval(100);
    QObject::connect(&d->timer, &QTimer::timeout, this, &QtEmbedAdapter::poll);
    d->lastStatus = status();
}

QtEmbedAdapter::~QtEmbedAdapter()
{
    // The owner must prevent deletion and HWND destruction until process exit.
    // On an unexpected deletion, join before destroying the worker to avoid
    // a use-after-free; this may block and cannot contain a spawned process.
    // The warning is diagnostic, not protection against forced shutdown.
    if (processTracked())
        qWarning("Sa6i Clean adapter destroyed while launch or process is tracked");
#if SA6I_HAVE_EMBED
    if (d->worker) d->worker->wait();
#endif
}

bool QtEmbedAdapter::onOwnerThread() const { return QThread::currentThread() == thread(); }
bool QtEmbedAdapter::supported() const { return SA6I_HAVE_EMBED; }
bool QtEmbedAdapter::initialized() const { return d->bound; }
bool QtEmbedAdapter::launchPending() const {
#if SA6I_HAVE_EMBED
    return d->worker != nullptr;
#else
    return false;
#endif
}
bool QtEmbedAdapter::processTracked() const {
#if SA6I_HAVE_EMBED
    return d->bound && (d->worker || d->host.process);
#else
    return false;
#endif
}
QString QtEmbedAdapter::status() const {
#if SA6I_HAVE_EMBED
    if (!d->bound) return QStringLiteral("unbound");
    if (d->worker) return d->closeDuringLaunch ? QStringLiteral("closing") : QStringLiteral("launching");
    switch (d->host.status) {
    case EMBED_IDLE: return QStringLiteral("idle");
    case EMBED_DISCOVERING: return QStringLiteral("discovering");
    case EMBED_ATTACHED: return QStringLiteral("attached");
    case EMBED_UNATTACHED: return QStringLiteral("unattached");
    case EMBED_CLOSING: return QStringLiteral("closing");
    case EMBED_CLOSED: return QStringLiteral("closed");
    }
    return QStringLiteral("unknown");
#else
    return QStringLiteral("unsupported");
#endif
}
QString QtEmbedAdapter::testProfile() const {
#if SA6I_HAVE_EMBED
    return d->bound ? QString::fromWCharArray(d->host.profile) : QString();
#else
    return QString();
#endif
}
quint32 QtEmbedAdapter::error() const {
#if SA6I_HAVE_EMBED
    return d->bound ? d->host.error : 0;
#else
    return 0;
#endif
}

void QtEmbedAdapter::updateAfterCall() {
    const bool tracked = processTracked();
#if SA6I_HAVE_EMBED
    // A worker completion is delivered by Qt; poll only once it hands back
    // the host. Do not concurrently touch the worker's copy.
    const bool pollProcess = d->bound && !d->worker && d->host.process;
#else
    const bool pollProcess = false;
#endif
    if (pollProcess && !d->timer.isActive()) d->timer.start();
    else if (!pollProcess && d->timer.isActive()) d->timer.stop();
    const QString currentStatus = status();
    const QString currentProfile = testProfile();
    const quint32 currentError = error();
    if (d->lastBound != d->bound || d->lastPending != launchPending() || d->lastTracked != tracked ||
        d->lastStatus != currentStatus || d->lastProfile != currentProfile || d->lastError != currentError) {
        d->lastBound = d->bound;
        d->lastPending = launchPending();
        d->lastTracked = tracked;
        d->lastStatus = currentStatus;
        d->lastProfile = currentProfile;
        d->lastError = currentError;
        emit changed();
    }
}

bool QtEmbedAdapter::bindNativeParent(quintptr hwnd) {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!hwnd || processTracked()) return false;
    const HWND parent = reinterpret_cast<HWND>(hwnd);
    EmbedHost candidate {};
    if (!embed_init(&candidate, parent)) return false;
    d->host = candidate;
    d->bound = true;
    updateAfterCall();
    return true;
#else
    Q_UNUSED(hwnd);
    return false;
#endif
}

bool QtEmbedAdapter::start(const QString &directory) {
    return startImpl(directory, 0);
}

bool QtEmbedAdapter::startWithTheme(const QString &directory, bool dark) {
    return startImpl(directory, dark ? 2 : 1);
}

bool QtEmbedAdapter::startImpl(const QString &directory, int initialTheme) {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!d->bound || processTracked() || d->host.status != EMBED_IDLE) return false;
    d->host.error = 0;
    d->closeDuringLaunch = false;
    EmbedHost launchHost = d->host;
    launchHost.initial_theme = initialTheme;
    // Separate experimental opt-in; never change normal application builds.
    launchHost.software_rendering = qEnvironmentVariableIntValue("SA6I_CLEAN_WIN7_SOFTWARE") == 1;
    auto *worker = new LaunchWorker(launchHost, directory.toStdWString(), this);
    d->worker = worker;
    QObject::connect(worker, &QThread::finished, this, [this, worker] {
        // Only the UI thread accesses d->host. The worker has stopped and its
        // process handle, if any, is transferred exactly once to the owner.
        const RECT latestRect = d->host.rect;
        const BOOL latestSelected = d->host.selected;
        d->host = worker->host;
        d->worker = nullptr;
        // The view may have moved or been hidden while verification ran.
        embed_set_rect(&d->host, &latestRect);
        embed_select(&d->host, latestSelected);
        if (d->closeDuringLaunch) {
            d->closeDuringLaunch = false;
            embed_request_close(&d->host);
        }
        worker->deleteLater();
        updateAfterCall();
    });
    worker->start();
    // QThread::start returns void; if OS thread creation failed, Qt may not
    // emit finished. A completed worker has entered run(), so don't confuse a
    // very fast successful run with that failure.
    if (!worker->isRunning() && !worker->entered.load(std::memory_order_acquire)) {
        d->worker = nullptr;
        d->host.error = ERROR_NOT_ENOUGH_MEMORY; // generic resource/start failure
        delete worker;
        updateAfterCall();
        return false;
    }
    updateAfterCall();
    return true;
#else
    Q_UNUSED(directory); Q_UNUSED(initialTheme);
    return false;
#endif
}

bool QtEmbedAdapter::setRect(int left, int top, int right, int bottom) {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!d->bound) return false;
    const RECT rect {left, top, right, bottom};
    const bool ok = embed_set_rect(&d->host, &rect);
    updateAfterCall();
    return ok;
#else
    Q_UNUSED(left); Q_UNUSED(top); Q_UNUSED(right); Q_UNUSED(bottom);
    return false;
#endif
}

bool QtEmbedAdapter::setSelected(bool selected) {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!d->bound || (d->worker && d->closeDuringLaunch)) return false;
    const bool ok = embed_select(&d->host, selected ? TRUE : FALSE);
    updateAfterCall();
    return ok;
#else
    Q_UNUSED(selected);
    return false;
#endif
}

void QtEmbedAdapter::poll() {
    if (!onOwnerThread()) return;
#if SA6I_HAVE_EMBED
    if (!d->bound || d->worker) return;
    embed_poll(&d->host);
    updateAfterCall();
#endif
}

bool QtEmbedAdapter::requestClose() {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!d->bound) return true; // No launch was possible without binding.
    if (d->worker) {
        // Record the pending hide on the GUI-thread host too. The worker's
        // copy will be reconciled with this state before discovery on handoff.
        // A caller that cancels may explicitly select the view again.
        embed_select(&d->host, FALSE);
        d->closeDuringLaunch = true;
        updateAfterCall();
        return false;
    }
    const bool done = embed_request_close(&d->host);
    updateAfterCall();
    return done;
#else
    return true; // Unsupported adapter never launches a process.
#endif
}

bool QtEmbedAdapter::cancelClose() {
    if (!onOwnerThread()) return false;
#if SA6I_HAVE_EMBED
    if (!d->bound) return false;
    if (d->worker) {
        if (!d->closeDuringLaunch) return false;
        d->closeDuringLaunch = false;
        updateAfterCall();
        return true;
    }
    const bool ok = embed_cancel_close(&d->host);
    updateAfterCall();
    return ok;
#else
    return false;
#endif
}
