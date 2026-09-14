import type { ReactElement } from "react";
import type { ProfileIdentity } from "../types/report";
import {
  BuildingIcon,
  ExternalLinkIcon,
  LinkIcon,
  MailIcon,
  MapPinIcon,
  TwitterIcon,
} from "./icons";

interface ProfileHeaderProps {
  identity: ProfileIdentity | null;
  username: string;
}

function initialsOf(name: string | null, username: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length > 0) {
      return parts
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase();
    }
  }
  return username.slice(0, 1).toUpperCase() || "?";
}

function formatAccountAge(createdAt: string | null): string | null {
  if (!createdAt) return null;
  const year = new Date(createdAt).getFullYear();
  if (Number.isNaN(year)) return null;
  return `On GitHub since ${year}`;
}

function DetailRow({
  icon,
  text,
  href,
}: {
  icon: ReactElement;
  text: string;
  href?: string;
}) {
  const content = href ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-2 text-sm text-muted hover:text-accent hover:underline transition-colors min-w-0"
    >
      {icon}
      <span className="truncate">{text}</span>
      <ExternalLinkIcon className="h-3 w-3 shrink-0" />
    </a>
  ) : (
    <span className="inline-flex items-center gap-2 text-sm text-muted min-w-0">
      {icon}
      <span className="truncate">{text}</span>
    </span>
  );
  return <div className="min-w-0">{content}</div>;
}

function ensureUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export function ProfileHeader({ identity, username }: ProfileHeaderProps) {
  const name = identity?.name ?? null;
  const htmlUrl = identity?.html_url ?? null;

  return (
    <section
      aria-label="Profile"
      className="bg-panel border border-border rounded-lg p-6 flex flex-col sm:flex-row gap-6"
    >
      {identity?.avatar_url ? (
        <img
          src={identity.avatar_url}
          alt={name ? `${name} (${username})` : `@${username}`}
          className="h-20 w-20 rounded-full border border-border shrink-0"
        />
      ) : (
        <div
          role="img"
          aria-label={`Avatar placeholder for ${username}`}
          className="h-20 w-20 rounded-full bg-accent/15 border border-border flex items-center justify-center text-2xl font-bold text-accent shrink-0"
        >
          {initialsOf(name, username)}
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
          <h2 className="text-2xl font-bold text-text truncate">
            {name ?? `@${username}`}
          </h2>
          {identity?.hireable && (
            <span className="mt-1 px-2 py-0.5 rounded-full bg-good/15 text-good text-xs font-semibold">
              Open to opportunities
            </span>
          )}
        </div>

        <a
          href={htmlUrl ?? `https://github.com/${username}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-muted hover:text-accent hover:underline transition-colors"
        >
          @{username}
          <ExternalLinkIcon className="h-3.5 w-3.5" />
        </a>

        {identity?.bio && (
          <p className="mt-2 text-sm text-text leading-relaxed">{identity.bio}</p>
        )}

        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
          {identity?.location && (
            <DetailRow icon={<MapPinIcon className="h-4 w-4 shrink-0" />} text={identity.location} />
          )}
          {identity?.company && (
            <DetailRow icon={<BuildingIcon className="h-4 w-4 shrink-0" />} text={identity.company} />
          )}
          {identity?.blog && (
            <DetailRow
              icon={<LinkIcon className="h-4 w-4 shrink-0" />}
              text={identity.blog}
              href={ensureUrl(identity.blog)}
            />
          )}
          {identity?.email && (
            <DetailRow
              icon={<MailIcon className="h-4 w-4 shrink-0" />}
              text={identity.email}
              href={`mailto:${identity.email}`}
            />
          )}
          {identity?.twitter_username && (
            <DetailRow
              icon={<TwitterIcon className="h-4 w-4 shrink-0" />}
              text={`@${identity.twitter_username}`}
              href={`https://x.com/${identity.twitter_username}`}
            />
          )}
        </div>

        {(() => {
          const accountAge = formatAccountAge(identity?.created_at ?? null);
          if (accountAge) {
            return (
              <p className="mt-3 text-xs text-muted">{accountAge}</p>
            );
          }
          return null;
        })()}
      </div>

      {identity === null && (
        <p className="text-sm text-muted">Profile details are unavailable.</p>
      )}
    </section>
  );
}
