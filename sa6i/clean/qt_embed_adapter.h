// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental adapter; wired into an opt-in Windows source build only.
// The full app has not been built or approved for release.
#pragma once

#include <QtCore/QObject>
#include <QtCore/QString>
#include <QtCore/QtGlobal>
#include <memory>

class QtEmbedAdapter final : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool supported READ supported CONSTANT)
    Q_PROPERTY(bool initialized READ initialized NOTIFY changed)
    Q_PROPERTY(bool launchPending READ launchPending NOTIFY changed)
    Q_PROPERTY(bool processTracked READ processTracked NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(QString testProfile READ testProfile NOTIFY changed)
    Q_PROPERTY(quint32 error READ error NOTIFY changed)
public:
    explicit QtEmbedAdapter(QObject *parent = nullptr);
    ~QtEmbedAdapter() override;

    bool supported() const;
    bool initialized() const;
    bool launchPending() const;
    bool processTracked() const;
    QString status() const;
    // Most recent newly created test profile, including after launch failure.
    // No automatic deletion: older directories can remain on disk.
    QString testProfile() const;
    quint32 error() const;

    // C++ owner only: bind the actual top-level HWND after creation. Never
    // call while a process is tracked. Rebinding is NOT reparenting a child.
    bool bindNativeParent(quintptr hwnd);

    // Schedules verification/launch on a worker. True means accepted, not
    // successfully launched; observe status/error. processTracked is also
    // true while launch is unresolved, before any process may exist.
    // All adapter methods must be called on its owning GUI thread.
    Q_INVOKABLE bool start(const QString &directory);
    // Initial theme for the experimental full fixture; future changes in the
    // host do not automatically propagate to an already-running child.
    Q_INVOKABLE bool startWithTheme(const QString &directory, bool dark);
    // Physical client pixels, already mapped/clipped by the owner.
    Q_INVOKABLE bool setRect(int left, int top, int right, int bottom);
    Q_INVOKABLE bool setSelected(bool selected);
    Q_INVOKABLE void poll();
    Q_INVOKABLE bool requestClose();
    Q_INVOKABLE bool cancelClose();

signals:
    void changed();

private:
    struct Impl;
    std::unique_ptr<Impl> d;
    bool onOwnerThread() const;
    bool startImpl(const QString &directory, int initialTheme);
    void updateAfterCall();
};
