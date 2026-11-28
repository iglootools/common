"""The repositories of the iglootools organization, as GitHub lists them."""

from dataclasses import dataclass

from iglootools.github.client import GitHub, Repository

ORGANIZATION = "iglootools"


@dataclass(frozen=True)
class OrganizationRepository:
    """A repository of the organization: its name, state and where to clone it from."""

    name: str
    archived: bool
    default_branch: str
    ssh_url: str
    https_url: str

    @property
    def repository(self) -> Repository:
        """Return it as the owner and name the GitHub client takes."""
        return Repository(ORGANIZATION, self.name)


def list_repositories(github: GitHub) -> list[OrganizationRepository]:
    """
    List every repository of the organization, archived ones included, by name.

    Raises GitHubError when GitHub cannot be asked.
    """
    return sorted(
        (
            OrganizationRepository(
                name=item["name"],
                archived=bool(item.get("archived")),
                default_branch=item.get("default_branch") or "main",
                ssh_url=item.get("ssh_url", ""),
                https_url=item.get("clone_url", ""),
            )
            for item in github.get_all(f"/orgs/{ORGANIZATION}/repos?type=all")
        ),
        key=lambda found: found.name,
    )
